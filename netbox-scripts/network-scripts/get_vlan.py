#!/home/netbox-scripter/netbox_venv/bin/python

import sys
sys.path.insert(1, '/home/netbox-scripter/netbox-git')
import config
import pynetbox
from ntc_templates.parse import parse_output
from netmiko import ConnectHandler
from concurrent.futures import ProcessPoolExecutor
import traceback

def create_vlans_netbox_on_huawei_vrp(device_name):

    nb = pynetbox.api(
        config.netbox_url,
        private_key_file=config.private_key_file_path_network,
        token=config.netbox_token,
        threading=True
    )
    vlan_number_count = 0
    vlan_destruction_count = 0
    vlan_updated_count = 0

    nb_device = nb.dcim.devices.get(name=device_name)
    nb_secret = nb.plugins.netbox_secretstore.secrets.get(device=device_name)

    if nb_device.platform.name == 'VRP' and nb_device.status.value == 'active':
        netmiko_device = {
            'device_type': 'huawei',
            'host': str(nb_device.primary_ip)[:-3:],
            'username': nb_secret.name,
            'password': nb_secret.plaintext,
            'port': 22,
            'secret': nb_secret.plaintext
        }
        net_connect = ConnectHandler(**netmiko_device)
        display_vlan_out = net_connect.send_command('display vlan\n')

        parsed_device_vlan = parse_output(platform="huawei_vrp", command="display vlan", data=display_vlan_out)

        device_vlan_list_all = []

        for device_vlan in parsed_device_vlan:
            display_vlan_out_verbose = net_connect.send_command(f"display vlan {device_vlan['vlan_id']} verbose\n")
            vlan_name_output_parser = parse_output(platform="huawei_vrp", command="display vlan verbose", data=display_vlan_out_verbose)

            vlan_name_output_parser = vlan_name_output_parser[0]
            vlan_name = [vlan_name_output_parser['vlan_id']]

            if str(vlan_name_output_parser['vlan_name']) == str(vlan_name_output_parser['description']):
                vlan_name.append(vlan_name_output_parser['vlan_name'])
            elif str(vlan_name_output_parser['vlan_name']) == 'VLAN' or str(vlan_name_output_parser['vlan_name']) == '':
                vlan_name.append(f"{vlan_name_output_parser['description']} {vlan_name_output_parser['vlan_id']}")
            else:
                vlan_name.append(f"{vlan_name_output_parser['vlan_name']} {vlan_name_output_parser['vlan_id']}")
            device_vlan_list_all.append(vlan_name)

        net_connect.disconnect()

        netbox_dcim_device_site_id = nb_device.site.id
        netbox_device_vlan_group = nb.ipam.vlan_groups.get(name=device_name)
        netbox_device_vlan_in_vlan_group = nb.ipam.vlans.filter(group_id=netbox_device_vlan_group.id)
        netbox_device_vlan_tuple = tuple(netbox_device_vlan_in_vlan_group)

        set_ipam_vlan = set()
        set_switch_vlan = set()

        for vlan in device_vlan_list_all:
            isvlan_exist = False
            set_switch_vlan.add(vlan[0])
            for netbox_device_ipam_vlan in netbox_device_vlan_tuple:
                set_ipam_vlan.add(str(netbox_device_ipam_vlan.vid))
                if str(netbox_device_ipam_vlan.vid) == vlan[0]:
                    isvlan_exist = True
                    try:
                        netbox_device_ipam_vlan.update({"name": vlan[1], 'status': 'active', 'vid': vlan[0]})
                        vlan_updated_count = vlan_updated_count + 1
                        break
                    except Exception:
                        print('Error! Device {}.'.format(device_name) + ' Error while updating vlan')
                        print('Ошибка:\n', traceback.format_exc())
            if not isvlan_exist:
                try:
                    nb.ipam.vlans.create(site = netbox_dcim_device_site_id, group = netbox_device_vlan_group.id, vid=vlan[0],
                                     name = vlan[1], status = 'active')
                except Exception:
                    print('Error! Device {}.'.format(device_name) + ' Error while creating vlan')
                    print('Ошибка:\n', traceback.format_exc())
                vlan_number_count = vlan_number_count + 1

        set_ipam_vlan.difference_update(set_switch_vlan)
        for removal_сandidate in set_ipam_vlan:
            delete_vlan_netbox=nb.ipam.vlans.get(group_id=netbox_device_vlan_group.id, vid=removal_сandidate)
            try:
                delete_vlan_netbox.delete()
                vlan_destruction_count = vlan_destruction_count + 1
            except Exception:
                print('Error: Device {}.'.format(device_name) + ' Error while deleting non extisting vlan')
                print('Ошибка:\n', traceback.format_exc())
    #print('Device: {};'.format(device_name)+' Script destroyed ', vlan_destruction_count, ' vlan;','Script create ', vlan_number_count, ' vlan;', 'Script update ', vlan_updated_count, ' vlan;')

def create_vlans_netbox_on_cisco_ios(device_name):

    nb = pynetbox.api(
        config.netbox_url,
        private_key_file=config.private_key_file_path_network,
        token=config.netbox_token,
        threading=True
    )

    vlan_number_count = 0
    vlan_destruction_count = 0
    vlan_updated_count = 0

    nb_device = nb.dcim.devices.get(name=device_name)
    nb_secret = nb.plugins.netbox_secretstore.secrets.get(device=device_name)

    if nb_device.platform.name == 'ios':

        netmiko_device = {
            'device_type': 'cisco_ios',
            'host': str(nb_device.primary_ip)[:-3:],
            'username': nb_secret.name,
            'password': nb_secret.plaintext,
            'port': 22,
            'secret': nb_secret.plaintext
        }
        net_connect = ConnectHandler(**netmiko_device)
        output = net_connect.send_command('show vlan')

        parsed_device_vlan = parse_output(platform="cisco_ios", command="show vlan", data=output)

        netbox_dcim_device_site_id = nb_device.site.id
        netbox_device_vlan_group = nb.ipam.vlan_groups.get(name=device_name)
        netbox_device_vlan_in_vlan_group = nb.ipam.vlans.filter(group_id=netbox_device_vlan_group.id)
        netbox_device_vlan_tuple = tuple(netbox_device_vlan_in_vlan_group)

        set_ipam_vlan = set()
        set_switch_vlan = set()

        net_connect.disconnect()

        for device_vlan in parsed_device_vlan:
            isvlan_exist = False
            if device_vlan['status'] in 'active':
                set_switch_vlan.add(device_vlan['vlan_id'])
                for netbox_device_ipam_vlan in netbox_device_vlan_tuple:
                    set_ipam_vlan.add(str(netbox_device_ipam_vlan.vid))
                    if str(netbox_device_ipam_vlan.vid) == device_vlan['vlan_id']:
                        isvlan_exist = True
                        try:
                            netbox_device_ipam_vlan.update({"name": device_vlan['name'], 'status': device_vlan['status'], 'vid': device_vlan['vlan_id']})
                            vlan_updated_count = vlan_updated_count + 1
                            break
                        except Exception:
                            print('Error! Device {}.'.format(device_name)+' Error while updating vlan')
                            print('Ошибка:\n', traceback.format_exc())

                if not isvlan_exist:
                    try:
                        nb.ipam.vlans.create(site=netbox_dcim_device_site_id, group=netbox_device_vlan_group.id, vid=device_vlan['vlan_id'], name=device_vlan['name'], status=device_vlan['status'])
                    except Exception:
                        print('Error! Device {}.'.format(device_name) + ' Error while creating vlan')
                        print('Ошибка:\n', traceback.format_exc())
                    vlan_number_count = vlan_number_count + 1

        set_ipam_vlan.difference_update(set_switch_vlan)

        for removal_сandidate in set_ipam_vlan:
            delete_vlan_netbox = nb.ipam.vlans.get(group_id=netbox_device_vlan_group.id, vid=removal_сandidate)
            try:
                delete_vlan_netbox.delete()
                vlan_destruction_count = vlan_destruction_count + 1
            except Exception:
                print('Error: Device {}.'.format(device_name) + ' Error while deleting non extisting vlan')
                print('Ошибка:\n', traceback.format_exc())

    #print('Device: {};'.format(device_name)+' Script destroyed ', vlan_destruction_count, ' vlan;','Script create ', vlan_number_count, ' vlan;','Script update ', vlan_updated_count, ' vlan;')

def create_vlans_netbox_on_cisco_ios_telnet(device_name):

    nb = pynetbox.api(
        config.netbox_url,
        private_key_file=config.private_key_file_path_network,
        token=config.netbox_token,
        threading=True
    )
    vlan_number_count = 0
    vlan_destruction_count = 0
    vlan_updated_count = 0

    nb_device = nb.dcim.devices.get(name=device_name)
    nb_secret = nb.plugins.netbox_secretstore.secrets.get(device=device_name)

    if nb_device.platform.name == 'ios_telnet':

        netmiko_device = {
            'device_type': 'cisco_ios_telnet',
            'host': str(nb_device.primary_ip)[:-3:],
            'username': nb_secret.name,
            'password': nb_secret.plaintext,
            'port': 23,
            'secret': nb_secret.plaintext
        }
        net_connect = ConnectHandler(**netmiko_device)
        output = net_connect.send_command('show vlan')

        parsed_device_vlan = parse_output(platform="cisco_ios", command="show vlan", data=output)

        netbox_dcim_device_site_id = nb_device.site.id
        netbox_device_vlan_group = nb.ipam.vlan_groups.get(name=device_name)
        netbox_device_vlan_in_vlan_group = nb.ipam.vlans.filter(group_id=netbox_device_vlan_group.id)
        netbox_device_vlan_tuple = tuple(netbox_device_vlan_in_vlan_group)

        set_ipam_vlan = set()
        set_switch_vlan = set()

        net_connect.disconnect()

        for device_vlan in parsed_device_vlan:
            isvlan_exist = False
            if device_vlan['status'] in 'active':
                set_switch_vlan.add(device_vlan['vlan_id'])
                for netbox_device_ipam_vlan in netbox_device_vlan_tuple:
                    set_ipam_vlan.add(str(netbox_device_ipam_vlan.vid))
                    if str(netbox_device_ipam_vlan.vid) == device_vlan['vlan_id']:
                        isvlan_exist = True
                        try:
                            netbox_device_ipam_vlan.update({"name": device_vlan['name'], 'status': device_vlan['status'],'vid': device_vlan['vlan_id']})
                            vlan_updated_count = vlan_updated_count + 1
                            break
                        except Exception:
                            print('Error! Device {}.'.format(device_name) + ' Error while updating vlan')
                            print('Ошибка:\n', traceback.format_exc())

                if not isvlan_exist:
                    try:
                        nb.ipam.vlans.create(site=netbox_dcim_device_site_id, group=netbox_device_vlan_group.id,
                                             vid=device_vlan['vlan_id'], name=device_vlan['name'],
                                             status=device_vlan['status'])
                    except Exception:
                        print('Error! Device {}.'.format(device_name) + ' Error while creating vlan')
                        print('Ошибка:\n', traceback.format_exc())
                    vlan_number_count = vlan_number_count + 1

        set_ipam_vlan.difference_update(set_switch_vlan)

        for removal_сandidate in set_ipam_vlan:
            delete_vlan_netbox = nb.ipam.vlans.get(group_id=netbox_device_vlan_group.id, vid=removal_сandidate)
            try:
                delete_vlan_netbox.delete()
                vlan_destruction_count = vlan_destruction_count + 1
            except Exception:
                print('Error: Device {}.'.format(device_name) + ' Error while deleting non extisting vlan')
                print('Ошибка:\n', traceback.format_exc())

    #print('Device: {};'.format(device_name) + ' Script destroyed ', vlan_destruction_count, ' vlan;', 'Script create ', vlan_number_count, ' vlan;', 'Script update ', vlan_updated_count, ' vlan;')

def create_vlans_netbox_on_cisco_nxos(device_name):

    nb = pynetbox.api(
        config.netbox_url,
        private_key_file=config.private_key_file_path_network,
        token=config.netbox_token,
        threading=True
    )
    vlan_number_count = 0
    vlan_destruction_count = 0
    vlan_updated_count = 0
    nb_device = nb.dcim.devices.get(name=device_name)
    nb_secret = nb.plugins.netbox_secretstore.secrets.get(device=device_name)

    if nb_device.platform.name == 'nxos':

        netmiko_device = {
            'device_type': 'cisco_nxos',
            'host': str(nb_device.primary_ip)[:-3:],
            'username': nb_secret.name,
            'password': nb_secret.plaintext,
            'port': 22,
            'secret': nb_secret.plaintext
        }
        net_connect = ConnectHandler(**netmiko_device)
        output = net_connect.send_command('show vlan brief')

        parsed_device_vlan = parse_output(platform="cisco_nxos", command="show vlan", data=output)

        netbox_dcim_device_site_id = nb_device.site.id
        netbox_device_vlan_group = nb.ipam.vlan_groups.get(name=device_name)
        netbox_device_vlan_in_vlan_group = nb.ipam.vlans.filter(group_id=netbox_device_vlan_group.id)
        netbox_device_vlan_tuple = tuple(netbox_device_vlan_in_vlan_group)

        set_ipam_vlan = set()
        set_switch_vlan = set()

        net_connect.disconnect()

        for device_vlan in parsed_device_vlan:
            isvlan_exist = False
            if device_vlan['status'] in 'active':
                set_switch_vlan.add(device_vlan['vlan_id'])
                for netbox_device_ipam_vlan in netbox_device_vlan_tuple:
                    set_ipam_vlan.add(str(netbox_device_ipam_vlan.vid))
                    if str(netbox_device_ipam_vlan.vid) == device_vlan['vlan_id']:
                        isvlan_exist = True
                        try:
                            netbox_device_ipam_vlan.update({"name": device_vlan['name'], 'status': device_vlan['status'], 'vid': device_vlan['vlan_id']})
                            vlan_updated_count = vlan_updated_count + 1
                            break
                        except Exception:
                            print('Error! Device {}.'.format(device_name) + ' Error while updating vlan')
                            print('Ошибка:\n', traceback.format_exc())

                if not isvlan_exist:
                    try:
                        nb.ipam.vlans.create(site=netbox_dcim_device_site_id, group=netbox_device_vlan_group.id,
                                             vid=device_vlan['vlan_id'], name=device_vlan['name'],
                                             status=device_vlan['status'])
                    except Exception:
                        print('Error! Device {}.'.format(device_name) + ' Error while creating vlan')
                        print('Ошибка:\n', traceback.format_exc())
                    vlan_number_count = vlan_number_count + 1

        set_ipam_vlan.difference_update(set_switch_vlan)

        for removal_сandidate in set_ipam_vlan:
            delete_vlan_netbox = nb.ipam.vlans.get(group_id=netbox_device_vlan_group.id, vid=removal_сandidate)
            try:
                delete_vlan_netbox.delete()
                vlan_destruction_count = vlan_destruction_count + 1
            except Exception:
                print('Error: Device {}.'.format(device_name) + ' Error while deleting non extisting vlan')
                print('Ошибка:\n', traceback.format_exc())

    #print('Device: {};'.format(device_name) + ' Script destroyed ', vlan_destruction_count, ' vlan;', 'Script create ', vlan_number_count, ' vlan;', 'Script update ', vlan_updated_count, ' vlan;')

def add_vlans_to_netbox():
    import time
    start_time = time.time()

    nb = pynetbox.api(
        config.netbox_url,
        private_key_file=config.private_key_file_path_network,
        token=config.netbox_token,
        threading=True
    )

    script_devices=[]
    netbox_all_devices=nb.dcim.devices.all()
    for netbox_device in netbox_all_devices:
        netbox_device_tags=str(netbox_device.tags)
        if 'itp_script' in netbox_device_tags:
            script_devices.append(netbox_device)

    with ProcessPoolExecutor(max_workers=50) as executor:
        for device in script_devices:
            if device.platform.name == 'ios':
                #print('Execute script for', device)
                future = executor.submit(create_vlans_netbox_on_cisco_ios, device.name)
                #create_vlans_netbox_on_cisco_ios(device.name)
            elif device.platform.name == 'ios_telnet':
                #print('Execute script for', device)
                future = executor.submit(create_vlans_netbox_on_cisco_ios_telnet, device.name)
                #create_vlans_netbox_on_cisco_ios_telnet(device.name)
            elif device.platform.name == 'nxos':
                #print('Execute script for', device)
                future = executor.submit(create_vlans_netbox_on_cisco_nxos, device.name)
                #create_vlans_netbox_on_cisco_nxos(device.name)
            elif device.platform.name == 'VRP':
                #print('Execute script for', device)
                future = executor.submit(create_vlans_netbox_on_huawei_vrp, device.name)
                #create_vlans_netbox_on_huawei_vrp(device.name)
            else:
                None
    print("--- %s seconds ---" % (time.time() - start_time))

if __name__ == "__main__":
    add_vlans_to_netbox()

