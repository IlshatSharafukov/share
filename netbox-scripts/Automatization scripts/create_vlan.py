import pynetbox
import sys
sys.path.insert(1, '/home/netbox-scripter/netbox-git')
import config
import paramiko
import time
import re
from concurrent.futures import ProcessPoolExecutor, as_completed

start_time = time.time()

nb = pynetbox.api(
    config.netbox_url,
    private_key_file=config.private_key_file_path_network,
    token=config.netbox_token
)

p = 0
i = 0

# Тут должен быть список сетевых устройств с интерфейсами, где необходимо протащить влан в формате:
# devices_interfaces = { 'Netbox_Device-name_first': {'Interface1: 'Fa0/1', 'Interface2: 'Fa0/2'},  'Netbox_Device-name_second': {'Interface1: 'Fa0/1', 'Interface2: 'Fa0/2'}}
devices_interfaces = {
}

myLists = {"set_vlans{}".format(i): {} for i in range(12)}

def delete_vlan(device,vlan_id):
    nb = pynetbox.api(
        config.netbox_url,
        private_key_file=config.private_key_file_path_network,
        token=config.netbox_token
    )

    nb_device = nb.dcim.devices.get(name=device)
    nb_secret = nb.plugins.netbox_secretstore.secrets.get(device=device)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=str(nb_device.primary_ip)[:-3:],
        username=nb_secret.name,
        password=nb_secret.plaintext,
        look_for_keys=False,
        allow_agent=False)

    remove_template = ['switchport trunk allowed vlan remove {}\n']

    with client.invoke_shell() as ssh:

        ssh.send('show vlan id {}\n'.format(vlan_id))
        time.sleep(2)
        result = ssh.recv(50000).decode('ascii')
        match = re.search('not found in current VLAN database', result)

        if match == None:
            vlan_state = ('Данный vlan занят' + device)
        else:
            vlan_state = ('Данный vlan свободен ' + device)

            ssh.send('terminal length 0\n')
            time.sleep(1)
            ssh.recv(1000)

            ssh.send('conf t\n')
            time.sleep(1)
            ssh.recv(1000)

            ssh.send('vlan {}\n'.format(vlan_id))
            time.sleep(1)
            ssh.recv(1000)

            ssh.send('show vlan id {}\n'.format(vlan_id))
            time.sleep(5)
            result = ssh.recv(50000).decode('ascii')
            interfaces_summary = re.findall('(\w{2,}\d*/\d*/\d*|\w{2,}/d*\d*|Po\d{1,})',result)

            for interface_number in interfaces_summary:
                ssh.send('conf t\n')
                time.sleep(1)
                ssh.recv(1000)

                ssh.send('Interface {}\n'.format(interface_number))
                print('Захожу в режим настройки интерфейса {}'.format(interface_number))
                time.sleep(1)
                ssh.recv(1000)

                z = ''.join(remove_template)
                ssh.send(z.format(vlan_id))
                print((''.join(remove_template)).format(vlan_id))
                time.sleep(1)
                ssh.recv(1000)

                ssh.send('end\n')
                time.sleep(1)
                ssh.recv(1000)
            ssh.close()

    return vlan_state


def create_vlan(device, vlan_id, vlan_name, int_list):
    nb = pynetbox.api(
        config.netbox_url,
        private_key_file=config.private_key_file_path_network,
        token=config.netbox_token
    )

    print('Execute create vlan function with vlan_id ', vlan_id, vlan_name, device)
    nb_device = nb.dcim.devices.get(name=device)
    nb_secret = nb.plugins.netbox_secretstore.secrets.get(device=device)
    vl_gr = nb.ipam.vlan_groups.get(name=device)
    nb.ipam.vlans.create(group=vl_gr.id, vid=vlan_id,
                         name=vlan_name, status='active')
    trunk_template = ['switchport trunk allowed vlan add {}\n']

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=str(nb_device.primary_ip)[:-3:],
        username=nb_secret.name,
        password=nb_secret.plaintext,
        look_for_keys=False,
        allow_agent=False,
        timeout=90)

    with client.invoke_shell() as ssh:
        ssh.send('conf t\n')
        time.sleep(3)
        ssh.recv(1000)


        ssh.send('vlan {}\n'.format(vlan_id))
        time.sleep(3)
        ssh.recv(1000)


        ssh.send('name {}\n'.format(vlan_name))
        # print('name {}\n'.format(vlan_name))
        time.sleep(3)
        ssh.recv(1000)


        ssh.send('end\n')
        time.sleep(3)
        ssh.recv(1000)


        for interface in int_list:
            ssh.send('conf t\n')
            time.sleep(3)
            ssh.recv(1000)

            ssh.send('Interface {}\n'.format(interface))
            print('Захожу в режим настройки интерфейса {}'.format(interface))
            time.sleep(3)
            ssh.recv(1000)

            x = ''.join(trunk_template)
            ssh.send(x.format(vlan_id))
            print('Прописываю vlanID на порту {}'.format(interface))
            time.sleep(3)
            ssh.recv(1000)

            ssh.send('end\n')
            time.sleep(3)
            ssh.recv(1000)

    create_vlan_state = ('Successfully ' + device)
    ssh.close()

    return (create_vlan_state)

def create_vlan_fun():
    p = 0
    vlan_name = input("Введите имя vlan'a: ")
    for device,int_number in devices_interfaces.items():
        vl_gr = nb.ipam.vlan_groups.get(name=device)
        vlans = nb.ipam.vlans.filter(group_id=vl_gr.id)
        vlan_list = []
        for vlan in vlans:
            vlan_list.append(vlan.vid)
        myLists['set_vlans{}'.format(p)] = vlan_list
        p = p + 1

    for i in range(600,1700):
        vlan_id = i
        if vlan_id not in myLists['set_vlans0'] and vlan_id not in myLists['set_vlans1'] and vlan_id not in myLists['set_vlans2'] and vlan_id not in myLists['set_vlans3'] and vlan_id not in myLists['set_vlans4'] and vlan_id not in myLists['set_vlans5'] and vlan_id not in myLists['set_vlans6'] and vlan_id not in myLists['set_vlans7'] and vlan_id not in myLists['set_vlans8'] and vlan_id not in myLists['set_vlans9'] and vlan_id not in myLists['set_vlans10']:
            break
        else:
            continue
    print('Свободный vlan = ', vlan_id)

    future_list = []
    future_list_2 = []
    int_list = []
    #print("starting point: ",time.time())

    with ProcessPoolExecutor(max_workers=20) as executor:
        for device,int_number in devices_interfaces.items():
            print('Захожу на железку {} чтобы УДАЛИТЬ выбранный vlanID с ненужных портов: '.format(device))
            future = executor.submit(delete_vlan,device,vlan_id)
        for f in as_completed(future_list):
            print(f.result())
        print('Vlans deleted')

    # Прописываем vlan
    with ProcessPoolExecutor(max_workers=20) as executor:
        for device_name,interface_dictionary in devices_interfaces.items():
            int_list = []
            for key1, interface in interface_dictionary.items():
                int_list.append(interface)
            device = device_name
            print("Настраиваю vlan на:", device, ";   Interface list ", int_list)
            future = executor.submit(create_vlan, device, vlan_id, vlan_name, int_list)
            #create_vlan(device,vlan_id,vlan_name,int_list)

        for fa in as_completed(future_list_2):
            print(fa.result())
        print('Vlans created')

    return vlan_id

if __name__ == "__main__":
    create_vlan_fun()