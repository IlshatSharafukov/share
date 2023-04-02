#!/home/netbox-scripter/netbox_venv/bin/python

from __future__ import print_function
from pyVim.connect import SmartConnect, Disconnect
import atexit
import json
import pynetbox
import sys
sys.path.insert(1, '/home/netbox-scripter/netbox-git')
import config

data = {}

#функция getNic используется для получения информации о виртуальных адаптерах каждой конкретной ВМ
def getNICs(summary, guest):
    nics = {}
    for nic in guest.net:
        if nic.network:  # Only return adapter backed interfaces
            if nic.ipConfig is not None and nic.ipConfig.ipAddress is not None:
                nics[nic.macAddress] = {}  # Use mac as uniq ID for nic
                nics[nic.macAddress]['netlabel'] = nic.network
                ipconf = nic.ipConfig.ipAddress
                i = 0
                nics[nic.macAddress]['ipv4'] = {}
                for ip in ipconf:
                    if ":" not in ip.ipAddress:  # Only grab ipv4 addresses
                        nics[nic.macAddress]['ipv4'][i] = ip.ipAddress
                        nics[nic.macAddress]['prefix'] = ip.prefixLength
                        nics[nic.macAddress]['connected'] = nic.connected
                i = i+1
    return nics


def vmsummary(summary, guest, storage, mem, hardware, snapshot):
    vmsum = {}
    config = summary.config
    net = getNICs(summary, guest)
    #оперативная память
    vmsum['mem'] = str(config.memorySizeMB / 1024)
    #сумма всех жестких дисков ВМ
    vmsum['diskGBTotal'] = round(int(float("%.2f" % (summary.storage.committed / 1024**3))))+round(int(float("%.2f" % (summary.storage.uncommitted / 1024**3))))
    #кол-во цпу
    vmsum['cpu'] = str(config.numCpu)
    #папка, в которой лежит вм
    vmsum['path'] = config.vmPathName
    #операционная система, на которой работает вм
    vmsum['ostype'] = config.guestFullName
    #состояние вм (вкл выкл)
    vmsum['state'] = summary.runtime.powerState
    #дескрипшн, который дописывают сами вертельщики.
    #здесь стоит отметить, что в аннотациях иногда содержатся пароли к ВМ. возможно этот кусок кода вообще следует удалить, т.к. мы его все равно пока что не используем
    vmsum['annotation'] = config.annotation if config.annotation else ''
    #в функцию net записывается результат выполнения функции getNic
    vmsum['net'] = net
    #общее кол-во сетевых интерфейсов
    vmsum['TotalNics'] = summary.config.numEthernetCards
    #осуществляется ли на данной ВМ резервация оперативной памяти (true or false)
    vmsum['MemoryReservation'] = mem
    j=0
    i=0
    k=0
    #следующий кусок кода необходим для определения количества и типов жестких дисков, прицепленных к каждой конкретной ВМ
    #метод vim.vm.VirtualHardware позволяет получить список всех виртуальных устройств, такие как жесткие диски, сетевые адаптеры, и т.д.
    for hard_disk in hardware:
        #далее в цикле мы вычленяем из всего мусора только жесткие диски
        if 'Hard disk' in hard_disk.deviceInfo.label:
            try:
                if hard_disk.backing.thinProvisioned == True:
                    vmsum['ThinProv'] = 'True'
                else:
                    vmsum['ThinProv'] = 'False'
            except AttributeError:
                vmsum['ThinProv'] = 'False'
            #следующим этапом является отделение RDM дисков от обычных (толстых или тонких)
            if 'independent_persistent' in hard_disk.backing.diskMode:
                #тут мы записываем хранилку, на которой томится данный rdm диск
                vmsum['RDM_DISK_info_{}'.format(j)] = hard_disk.backing.fileName
                #тут мы фиксируем объем данного диска
                vmsum['RDM_DISK_Total_{}'.format(j)] = ("%.2f" % (hard_disk.capacityInKB // 1024**2))
                j=j+1
            else:
                #оставшийся кусок кода делает тоже самое, но уже для всех остальных дисков (НЕ rdm)
                vmsum['Storage_info_{}'.format(i)] = hard_disk.backing.fileName
                vmsum['Storage_TotalDisk_{}'.format(i)]= ("%.2f" % (hard_disk.capacityInKB // 1024**2))
                i=i+1
        #разобравшись с жесткими дисками, вычленяем сетевые адаптеры и записываем их мак адреса
        elif 'Network adapter' in hard_disk.deviceInfo.label:
            vmsum['network_adapter_{}'.format(k)] = hard_disk.macAddress
            k=k+1
    #следующими тремя строками фиксируем количество rdm дисков, количество других жестких дисков, кол-во сетевых адаптеров
    #это пригодится нам в дальнейшем (в следующих скриптах)
    vmsum['RDM_index_num']=j
    vmsum['Storage_index_num']=i
    vmsum['network_index_num']=k
    #методом snapshot определяем есть ли на тачке СНАПШОТ
    if snapshot != None:
        vmsum['Snapshot'] = 'True'
    else:
        vmsum['Snapshot'] = 'False'

    return vmsum
    #Возникает вопрос, зачем выдергивать сетевые адаптеры отдельно, если это делает функция getNic
    #Ответ: результат, который выдает функция getNic не всегда является корректным
    #т.е. если ВМ выключена, результат выполнения данной функции может оказаться пустым
    #В иных случаях данная функция возвращает нечитаемые символы, которые нельзя декодировать и соотв. никак нельзя использовать
    #но все таки иногда она выдает полную информацию о ВМ включая ipv4 адреса, мак адреса и vlan.
    #как эту информациию использовать я ещё не придумал, но возможно придумаю в дальнейшем. поэтому функцию getNic я не удаляю
    #баги функции getNic связаны с тулзами, которые установлены\не установлены на виртуалках. так же это зависит от версии тулзов.
    # с последними версиями все работает корректно, но последние версии стоят далеко не везде

#функцией  vm2dict формируем словарь из всех переменных, которые были получены нами ранее
def vm2dict(dc, cluster, host, vm, summary):
    # If nested folder path is required, split into a separate function
    vmname = vm.summary.config.name
    data[dc][cluster][host][vmname]['folder'] = vm.parent.name
    data[dc][cluster][host][vmname]['mem'] = summary['mem']
    data[dc][cluster][host][vmname]['diskGBTotal'] = summary['diskGBTotal']
    data[dc][cluster][host][vmname]['cpu'] = summary['cpu']
    data[dc][cluster][host][vmname]['path'] = summary['path']
    data[dc][cluster][host][vmname]['net'] = summary['net']
    data[dc][cluster][host][vmname]['ostype'] = summary['ostype']
    data[dc][cluster][host][vmname]['state'] = summary['state']
    data[dc][cluster][host][vmname]['annotation'] = summary['annotation']
    data[dc][cluster][host][vmname]['TotalNics'] = summary['TotalNics']
    data[dc][cluster][host][vmname]['RDM_index_num'] = summary['RDM_index_num']
    data[dc][cluster][host][vmname]['ThinProv'] = summary['ThinProv']
    data[dc][cluster][host][vmname]['Storage_index_num'] = summary['Storage_index_num']
    data[dc][cluster][host][vmname]['MemoryReservation'] = summary['MemoryReservation']
    data[dc][cluster][host][vmname]['network_index_num'] = summary['network_index_num']
    for i in range(summary['Storage_index_num']):
        data[dc][cluster][host][vmname]['Storage_info_{}'.format(i)] = summary['Storage_info_{}'.format(i)]
        data[dc][cluster][host][vmname]['Storage_TotalDisk_{}'.format(i)] = summary['Storage_TotalDisk_{}'.format(i)]
    if summary['RDM_index_num'] > 0:
        for k in range(summary['RDM_index_num']):
            data[dc][cluster][host][vmname]['RDM_DISK_info_{}'.format(k)] = summary['RDM_DISK_info_{}'.format(k)]
            data[dc][cluster][host][vmname]['RDM_DISK_Total_{}'.format(k)] = summary['RDM_DISK_Total_{}'.format(k)]
    data[dc][cluster][host][vmname]['Snapshot'] = summary['Snapshot']
    for m in range(summary['network_index_num']):
        data[dc][cluster][host][vmname]['network_adapter_{}'.format(m)]=summary['network_adapter_{}'.format(m)]

def data2json(data, args):
    with open(args.jsonfile, 'w') as f:
        json.dump(data, f)


def main():
    #в первую очередь определяется вцентр, к которому мы будем коннектиться
    dc_all = []

    for device_name in dc_all:
        #далее указываются параметры подключения к нетбоксу,
        #такие как api токен, ip нетбокса и т.д.
        #данные параметры хранятся в скрипте config.py
        nb = pynetbox.api(
            config.netbox_url,
            private_key_file=config.private_key_file_path,
            token=config.netbox_token

        )

        #далее, используя библиотеку pynetbox и встроенное api нетбокса
        #получаем класс, содержащий в себе 2 метода для получения username и password для входа в VC
        #логопасс был заранее внесен в нетбокс https://netbox.itpark.local/dcim/devices/102/
        nb_secret = nb.plugins.netbox_secretstore.secrets.get(device=device_name)
        #после получения необходимых исходных данных, коннектимся к вцентру
        si = SmartConnect(host='',
                               user=nb_secret.name,
                               disableSslCertValidation=True,
                               pwd=nb_secret.plaintext,
                               port=int('443'))
        if not si:
            print("Could not connect to the specified host using specified "
                  "username and password")
            return -1
        #следующие несколько строк являются для меня потемками, т.к. этот кусок кода был найден мной на просторах сети интернет
        #однако, автор оказался предусмотрительным и вставил свои комментарии
        atexit.register(Disconnect, si)

        content = si.RetrieveContent()
        children = content.rootFolder.childEntity
        for child in children:  # Iterate though DataCenters
            dc = child
            data[dc.name] = {}  # Add data Centers to data dict
            clusters = dc.hostFolder.childEntity
            for cluster in clusters:  # Iterate through the clusters in the DC
                # Add Clusters to data dict
                data[dc.name][cluster.name] = {}
                hosts = cluster.host  # Variable to make pep8 compliance
                for host in hosts:  # Iterate through Hosts in the Cluster
                    hostname = host.summary.config.name
                    # Add VMs to data dict by config name
                    data[dc.name][cluster.name][hostname] = {}
                    vms = host.vm
                    for vm in vms:  # Iterate through each VM on the host
                        vmname = vm.summary.config.name
                        data[dc.name][cluster.name][hostname][vmname] = {}
                        # функции summary передаем аргументы, относящиеся к конкретной ВМ
                        # и которые используются в дальнейшем
                        #api vmware которое использовалось в этом скрипте:
                        #https://vdc-download.vmware.com/vmwb-repository/dcr-public/6b586ed2-655c-49d9-9029-bc416323cb22/fa0b429a-a695-4c11-b7d2-2cbc284049dc/doc/vim.VirtualMachine.html#field_detail
                        summary = vmsummary(vm.summary, vm.guest, vm.storage.perDatastoreUsage,
                                            vm.config.memoryReservationLockedToMax, vm.config.hardware.device,
                                            vm.snapshot)
                        #получив всю необходимую информацию, формируем словарь, который в дальнейшем преобразовывается в json файлик
                        vm2dict(dc.name, cluster.name, hostname, vm, summary)

    sys.stdout = open("output.json", "w")
    print(json.dumps(data, sort_keys=True, indent=4))
    sys.stdout.close()

# Start program
if __name__ == "__main__":
    main()