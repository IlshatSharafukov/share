#!/home/netbox-scripter/netbox_venv/bin/python

import json
import sys
sys.path.insert(1, '/home/netbox-scripter/netbox-git')
import config
import pynetbox
import re
import time
import traceback

start_time = time.time()
#данный скрипт является вторым в общей логике заноса всех виртуалок на нетбокс
#его суть заключается в том, что он открывает файлик output.json,
#и далее происходит обработка всей информации о виртуальных машинах,
# которые содержатся в этом файлике с дальнейшим заносом этой инфы в нетбокс


with open('output.json') as f:
    templates = json.load(f)

nb = pynetbox.api(
    config.netbox_url,
    private_key_file=config.private_key_file_path,
    token=config.netbox_token
)

cluster_all = nb.virtualization.clusters.all()
cluster_all_tuple = tuple(cluster_all)
cluster_type_dc = nb.virtualization.cluster_types.get(name='')


for dc in templates:
    for cluster in templates[dc]:
        #определяем 2 пустых множества
        #это необходимо чтобы в дальнейшем удалять ВМ с нетбокса, которые были удалены на виртуализации
        #эта логика будет определяться в самом конце скрипта, о ней я напишу отдельно
        set_ipam_vm = set()
        set_vmware_vm = set()


        iscluster_exist = False
        for nb_cluster in cluster_all_tuple:
            if str(cluster) == str(nb_cluster.name):
                try:
                    iscluster_exist = True
                    #print(f'Cluster {cluster} is exist. Nothing to do')
                    break
                except Exception:
                    print(f'Error!. Error while update VM Cluster. If you want to has detail, watch this: {cluster}')
                    print('Error:\n', traceback.format_exc())
        if not iscluster_exist:
                try:
                    nb.virtualization.clusters.create(name=str(cluster), type=cluster_type_dc.id)
                    #print(f'This VM Cluster is not exist. Create Cluster with name: {cluster}')
                except Exception:
                    print(f'Error! Error while create VM Cluster. If you want to has detail, watch this: {cluster}')
                    print('Error:\n', traceback.format_exc())
        #print(cluster)
        cluster_get = nb.virtualization.clusters.get(name=cluster)
        vm_all = nb.virtualization.virtual_machines.filter(cluster_id=cluster_get.id)
        vm_all_tuple = tuple(vm_all)
        #print(vm_all_tuple)

        for host in templates[dc][cluster]:
                for vm in templates[dc][cluster][host]:
                    #далее начинается самое интересное, здесь мы начинаем фиксировать значения переменных,
                    #которые содержат различную информациию о ВМ, чтобы в дальнейшем нам было чем оперировать
                    mem = (templates[dc][cluster][host][vm]['mem'])
                    cpu = (templates[dc][cluster][host][vm]['cpu'])
                    path = (templates[dc][cluster][host][vm]['path'])
                    ostype = (templates[dc][cluster][host][vm]['ostype'])
                    state = (templates[dc][cluster][host][vm]['state'])
                    diskGBTotal = str(templates[dc][cluster][host][vm]['diskGBTotal'])
                    annotation = (templates[dc][cluster][host][vm]['annotation'])
                    netstate = templates[dc][cluster][host][vm]['net']
                    folder = templates[dc][cluster][host][vm]['folder']
                    folder = folder.rstrip(' ')
                    mem_res = templates[dc][cluster][host][vm]['MemoryReservation']
                    Storage_index_num = templates[dc][cluster][host][vm]['Storage_index_num']
                    RDM_index_num = templates[dc][cluster][host][vm]['RDM_index_num']
                    snapshot = templates[dc][cluster][host][vm]['Snapshot']
                    thinprov = templates[dc][cluster][host][vm]['ThinProv']

                    #определяем состояние переменной State
                    #данная переменная говорит нам о том, включена или выключена ВМ
                    if state == 'poweredOn':
                        status = 'active'
                    elif state == 'poweredOff':
                        status = 'offline'
                    else:
                        None

                    # аналогично определяем состояние переменной snapshot
                    # данная переменная говорит нам о том, есть или нет СНАПШОТ на ВМ
                    if snapshot == 'True':
                        snapshot = 1
                    elif snapshot == 'False':
                        snapshot = 0
                    else:
                        None


                    if thinprov == 'True':
                        thinprov = 1
                    elif thinprov == 'False':
                        thinprov = 0
                    else:
                        None

                    #следующим куском кода мы будем проверять наличие или отсутствие операционной системы на нетбоксе
                    #http://netbox.dc16.ru/dcim/platforms/

                    isplatform_exist = False
                    platform_all = nb.dcim.platforms.all()
                    for nb_platform in platform_all:
                        try:
                            name_short_os = str(ostype).replace(' ', '')
                            name_short_os_nb = str(nb_platform.name).replace(' ', '')
                            if str(name_short_os_nb) == str(name_short_os):
                                isplatform_exist = True
                                #print('OS под названием {} уже существует'.format(ostype))
                                break
                        except Exception:
                            print(f'Error! Error while update VM Platform. If you want to has detail, watch this: {name_short_os}')
                            print('Error:\n', traceback.format_exc())

                    if not isplatform_exist:
                        try:
                            slug_create = ostype.replace(' ', '')
                            # slug_create = pytils.translit.translify(slug_create)
                            slug_create = slug_create.replace('.', '')
                            slug_create = slug_create.replace("'", '')
                            slug_create = slug_create.replace('(', '')
                            slug_create = slug_create.replace(")", '')
                            # slug_create = slug_create[:100]
                            slug_create = slug_create.replace('"', '')
                            slug_create = slug_create.replace('+', '')
                            slug_create = slug_create.replace('/', '')
                            nb.dcim.platforms.create(name=str(ostype), slug=str(slug_create))
                            #print(f'This VM Platform is not exist. Create Platform with name: {ostype}')
                        except Exception:
                            print(f'Error! Error while create VM Platform. If you want to has detail, watch this: {ostype}')
                            print('Error:\n', traceback.format_exc())

                    #следующие переменные SSD,SATA...обнуляются т.к. все ВМ имеют разные размеры
                    #и при каждой новой итерации цикла эти переменные должны быть нулевыми
                    SSD = 0
                    SATA = 0
                    DEPR = 0
                    SAS = 0
                    #отдельно следует отметить переменную Unknown, она нужна для того если жесткий диск не попадет ни в один из представленных критериев
                    #сами критерии выбора будут определены ниже
                    Unknown = 0

                    #в первую очередь будем исходить из КОЛИЧЕСТВА жестких дисков
                    #сами диски на вм имеют следующий вид:
                    #Storage_info_xxx и Storage_TotalDisk_xxx
                    #где info это путь к датастору (например DC_veeam_v8/DC_veeam_v8.vmdk)
                    #а TotalDisk это общий объем данного жесткого диска
                    # соответственно, когда мы начинаем крутить цикл, то просто по очереди перебираем все диски на ВМ

                    dict_for_netbox = []

                    for i in range(Storage_index_num):
                        dict_for_netbox.append('Storage_{}'.format(i))
                        dict_for_netbox.append('Storage_volume_{}'.format(i))

                    r1 = dict.fromkeys(dict_for_netbox)
                    for i in range(Storage_index_num):
                        current_storage_volume_index = ('Storage_info_{}').format(i)
                        current_storage_index = ('Storage_TotalDisk_{}').format(i)
                        #в этом месте мы обращаемся к файлику output.json и записываем в переменную current_storage актуальную инфу о диске
                        #хз насколько получается понятно, надеюсь вы разберетесь
                        current_storage_info = templates[dc][cluster][host][vm]['{}'.format(current_storage_volume_index)]
                        current_storage_total = templates[dc][cluster][host][vm]['{}'.format(current_storage_index)]

                        current_storage_for_nb='Storage_{}'.format(i)
                        current_volume_for_nb ='Storage_volume_{}'.format(i)

                        r1.update({current_storage_for_nb: current_storage_info})
                        r1.update({current_volume_for_nb: current_storage_total})


                        #в этом месте мы определяем регулярные выражения, которые будут использоваться для выбора принадлежности диска (SAS, SATA, SSD)
                        # делаем мы это за счет того, что датастор 100% содержит в себе одно из этих слов
                        #например [DE4K2-SC-SAS4-MinFin] CLNT-SecMinFin-Sec/CLNT-SecMinFin-Sec.vmx
                        # такой гранулярности нам вполне достаточно чтобы понять к какой категории отнести текущий диск
                        reg_SSD = re.findall((r'SSD'), current_storage_info)
                        reg_SATA = re.findall((r'SATA'), current_storage_info)
                        reg_SAS = re.findall((r'SAS'), current_storage_info)

                        #тут мы ищем совпадения с регулярным выражением
                        #если совпадения есть, то прибавляем к обнуленной переменной общий объем текущего диска
                        if len(reg_SATA) != 0:
                            SATA = SATA + int(float(current_storage_total))
                        elif len(reg_SAS) != 0:
                            SAS = SAS + int(float(current_storage_total))
                        elif len(reg_SSD) != 0:
                            SSD = SSD + int(float(current_storage_total))
                        else:
                            Unknown = Unknown + int(float(current_storage_total))

                    #следующим условием мы отсекаем от общей массы так называемые RDM диски, которые следует учитывать отдельно, т.к
                    #они НЕ хранятся в переменных вида Storage_info_xxx и Storage_TotalDisk_xxx
                    #данные переменные имеют следующий вид:
                    #RDM_DISK_info_xxx и RDM_DISK_Total_xxx
                    # остальном логика абсолютно идентична предыдущему процессу для обычных жестких дисков
                    r2 = dict()
                    if RDM_index_num != 0:
                        dict_for_netbox_rdm = []
                        for m in range(RDM_index_num):
                            dict_for_netbox_rdm.append('Storage_rdm_{}'.format(m))
                            dict_for_netbox_rdm.append('Storage_volume_rdm{}'.format(m))

                        r2 = dict.fromkeys(dict_for_netbox_rdm)

                        for j in range(RDM_index_num):
                            # Info - это [V7K4-SAS-1] DC_veeam_v8/DC_veeam_v8.vmdk
                            RDM_storage_volume_index = ('RDM_DISK_info_{}').format(j)
                            # Total - это ВЕС в ГБ (51 ГБ)
                            RDM_storage_index = ('RDM_DISK_Total_{}').format(j)
                            # в этом месте мы обращаемся к файлику output.json и записываем в переменную current_storage актуальную инфу о диске
                            rdm_current_storage_info = templates[dc][cluster][host][vm][
                                '{}'.format(RDM_storage_volume_index)]
                            rdm_current_storage_total = templates[dc][cluster][host][vm][
                                '{}'.format(RDM_storage_index)]

                            current_storage_for_nb_rdm = 'Storage_rdm_{}'.format(j)
                            current_volume_for_nb_rdm = 'Storage_volume_rdm{}'.format(j)

                            r2.update({current_storage_for_nb_rdm: rdm_current_storage_info})
                            r2.update({current_volume_for_nb_rdm: rdm_current_storage_total})

                            #опять определяем регулярки
                            reg_SSD = re.findall((r'SSD'), rdm_current_storage_info)
                            reg_SATA = re.findall((r'SATA'), rdm_current_storage_info)
                            reg_SAS = re.findall((r'SAS'), rdm_current_storage_info)
                            #ищем совпадения. если таковые имеются, прибавляем объем диска к одной из переменных (SAS,SATA...)
                            if len(reg_SATA) != 0:
                                SATA = SATA + int(float(rdm_current_storage_total))
                            elif len(reg_SAS) != 0:
                                SAS = SAS + int(float(rdm_current_storage_total))
                            elif len(reg_SSD) != 0:
                                SSD = SSD + int(float(rdm_current_storage_total))
                            else:
                                Unknown = Unknown + int(float(rdm_current_storage_total))
                    #после всех манипуляций с дисками ВМ получаем общую сумму всех жестких дисков
                    total_disk_gb = int(SAS) + int(SATA) + int(SSD) + int(Unknown)
                    isvm_exist = False
                    #выдергиваем с нетбокса платформу, на которой работает ВМ (это нужно для создания новых виртуалок)
                    platform_current = nb.dcim.platforms.get(name=ostype)
                    #записываем текущую ВМ в переменную set_vmware_vm (в этот список попадают только те ВМ, которые есть на виртуализации на момент работы скрипта)
                    set_vmware_vm.add(str(vm))

                    r1.update(r2)

                    for vm_netbox in vm_all_tuple:
                        #далее мы начинаем прокручивать цикл для ВСЕХ вм которые есть в нетбоксе, чтобы найти или НЕ найти совпадения с текущей ВМ которая была взята с ВМВАРЫ
                        #в эту переменную set_ipam_vm мы записывыаем текущую ВМ которая была содрана с нетбокса
                        #зачем это нужно? ответ на этот вопрос будет дан ниже
                        set_ipam_vm.add(str(vm_netbox))
                        if str(vm_netbox.name) == str(vm[:64]):
                            try:
                                # очень важный момент! метод update в нетбоксе работает ТОЛЬКО со словарями.
                                # поэтому перед тем, как применять этот метод, я формирую словарь с исходными данными, которые будут заливаться в нетбокс
                                isvm_exist = True
                                tenant_for_vm = nb.tenancy.tenants.get(name=str(folder[:30]))
                                update_dict = dict(
                                    vcpus=cpu,
                                    memory=int(float(mem)),
                                    disk=total_disk_gb,
                                    tenant=tenant_for_vm,
                                    platform=platform_current,
                                    status=str(status)
                                )
                                vm_netbox.update({'custom_fields': {'HOST': str(host), 'SAS': int(SAS), 'SSD': int(SSD),
                                                                    'SATA': int(SATA), 'Unknown': int(Unknown),
                                                                    'Snapshot': bool(snapshot),
                                                                    'Thin Provision': bool(thinprov)}})
                                vm_netbox.update(update_dict)
                                #print('VM обновлена {}'.format(str(vm)))
                                break
                            except Exception:
                                print(f'Error!. Error while update VM in Cluster. If you want to has detail, watch this: {vm_netbox}')
                                print('Error:\n', traceback.format_exc())

                    if not isvm_exist:
                        try:
                            # в случае, когда вм нужно СОЗДАТЬ, а не обновить, работает практически такая же логика
                            # только в этот раз словарь мы уже не используем, а передаем аргументы напрямую
                            tenant_for_netbox = str(((folder[:30]).rstrip(' ')))
                            tenant_for_vm = nb.tenancy.tenants.get(name=tenant_for_netbox)
                            cluster_for_vm = nb.virtualization.clusters.get(name=str(cluster))
                            nb.virtualization.virtual_machines.create(name=str(vm[:64]),
                                                                      cluster=cluster_for_vm.id,
                                                                      vcpus=cpu,
                                                                      memory=int(float(mem)),
                                                                      disk=total_disk_gb,
                                                                      platform=platform_current.id,
                                                                      tenant=tenant_for_vm.id,
                                                                      status=str(status),
                                                                      custom_fields={'HOST': str(host), 'SAS': int(SAS),
                                                                                     'SSD': int(SSD), 'SATA': int(SATA),
                                                                                     'Unknown': int(Unknown),
                                                                                     'Snapshot': bool(snapshot),
                                                                                     'Thin Provision': bool(thinprov)}
                                                                      )
                            #print('VM создана {}'.format(str(vm)))
                        except Exception:
                            print(f'Error!. Error while create VM in Cluster. If you want to has detail, watch this: {vm[:64]}')
                            print('Error:\n', traceback.format_exc())


        #дальше, после того как все вм на хосту были обработаны, мы имеем 2 списка
        #set_ipam_vm и set_vmware_vm
        #первый содержит название всех виртуалок из нетбокса, второй всех вм на виртуализации
        #применив метод difference_update к одному из списков мы получим разницу, которая будет содержать в себе ВМ, которых нет на вмваре, но есть на нетбоксе
        #например: раньше на вмваре была vm под названием test_xxx. после прогона скрипта она была занесена в нетбокс
        #но в один из дней эту ВМ удалили, и получается так что её уже нет на виртуализации, но она есть в нетбоксе.
        #именно эту разницу мы и пытаемся отловить с помощью метода difference_update
        new_set=set_ipam_vm.difference(set_vmware_vm)
        #цикл представленный ниже мы будем прогонять для всех кандитатов на удаление в полученном списке
        for removal_сandidate in new_set:
            try:
                #print(removal_сandidate)
                # выдергиваем из нетбокса объект ВМ, который в дальнейшем надо будет удалить
                delete_vm_netbox = nb.virtualization.virtual_machines.get(name=removal_сandidate, cluster_id=cluster_get.id)
                #print(delete_vm_netbox)
                # выдергиваем из нетбокса ip адреса, которые связаны с этой удаляемой ВМ
                ip_removal = nb.ipam.ip_addresses.filter(virtual_machine=str(removal_сandidate))
                # и далее для каждого ip подходящего под эти условия прогоняем цикл
                for every_ip in ip_removal:
                    # двумя следующими действиями мы УДАЛЯЕМ вм из объекта ip address
                    # зачем это нужно: при удалении ВМ нетбокс удаляет ВСЕ связанные с данной ВМ объекты, включая интерфейсы и даже ip адреса
                    # ip адреса удалять не нужно, потому что там иногда содержатся очень важные сведения (description)
                    # поэтому мы сначала отделяем зерна от плевел, и со спокойной душой удяляем ВМ
                    update_dict = dict(assigned_object_id=0)
                    every_ip.update(update_dict)
                #print('удаляю ', delete_vm_netbox)
                delete_vm_netbox.delete()
            except Exception:
                print(f'Error!. Error while delete VM in Cluster. If you want to has detail, watch this: {removal_сandidate}')
                print('Error:\n', traceback.format_exc())

            #весь процесс повторяется для ВСЕХ хостов, всех кластеров, всех ДЦ

print("--- %s seconds ---" % (time.time() - start_time))