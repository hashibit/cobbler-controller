import time
import subprocess

from xmlrpc.client import ServerProxy
from netaddr import *

from werkzeug.local import LocalProxy
from flask import current_app

logger = LocalProxy(lambda: current_app.logger)

from . import errors
from . import ipmi
from . import retry


cobbler_1 = ServerProxy("http://192.168.1.10/cobbler_api")
cobbler_2 = ServerProxy("http://192.168.1.11/cobbler_api")

network_cobblers = {
    "192.168.1.0": cobbler_1,
    "192.168.2.0": cobbler_2,
}

cobblers = [
    cobbler_1,
    cobbler_2,
]

default_profile = "CentOS-7-Minimal-1708-x86_64"
default_ks_file = "/var/lib/cobbler/kickstarts/CentOS-7-Minimal-1708-x86_64.cfg"

cached_systems = []


def _find_cobbler_api(cidr):
    network = str(IPNetwork(cidr).network)

    if network in network_cobblers:
        return network_cobblers[network]
    return None



@retry(3, 2)
def _login(cobbler_api):
    return cobbler_api.login("cobbler", "cobbler")


def clear_cached_systems(f):
    def inner(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        finally:
            # logger.debug('clearing systems cache.')

            global cached_systems
            cached_systems = []

    return inner


def get_all_system_names():
    systems = get_all_systems()
    return sorted([system['name'] for system in systems])


def get_all_systems():
    global cached_systems

    if not cached_systems:
        # logger.debug('no cached systems, populate them.')
        system_dict = {}

        all_systems = []
        for cobbler_api in cobblers:
            try:
                all_systems = all_systems + cobbler_api.get_systems()
            except:
                logger.debug('error while cobbler_api.get_systems(), cobbler_api is: %s' % cobbler_api)
                import traceback; traceback.print_exc();
                pass

        for system in all_systems:
            if system['name'] not in system_dict:
                system_dict[system['name']] = system
            else:
                logger.warn("system name %s exists in both cobbler_api server." % (system['name']))

        cached_systems = [v for v in system_dict.values()]

    else:
        # logger.debug('hit cached systems, use them.')
        pass

    return cached_systems


def get_system(system_name=None, system_ip=None):
    if not system_name and not system_ip:
        return None

    systems = get_all_systems()
    logger.debug('system_name: %s, system_ip: %s' % (system_name, system_ip))
    # logger.debug('systems: %s' % systems)

    for system in systems:
        if system_name and system['name'] == system_name:
            return system

        if system_ip:
            for name, attrs in system['interfaces'].items():
                if attrs['ip_address'] == system_ip:
                    return system

    return None


@clear_cached_systems
def create_system(system_name,
                  system_profile,
                  system_ks_file,
                  system_interface,
                  interface_name,
                  interface_cidr,
                  interface_mac,
                  interface_dns,
                  interface_gateway,
                  ipmi_username,
                  ipmi_password,
                  ipmi_address):

    ipa = IPNetwork(interface_cidr)
    ip = str(ipa.ip)
    netmask = str(ipa.netmask)

    cobbler_api = _find_cobbler_api(interface_cidr)
    if not cobbler_api:
        raise errors.InterfaceIPUnsupported(interface_cidr)

    token = _login(cobbler_api)

    system_id = cobbler_api.new_system(token)

    cobbler_api.modify_system(system_id, "name", system_name, token)
    cobbler_api.modify_system(system_id, "hostname", system_name, token)
    cobbler_api.modify_system(system_id, "profile", system_profile, token)
    cobbler_api.modify_system(system_id, "kickstart", system_ks_file, token)

    cobbler_api.modify_system(system_id, "modify_interface", {
        "macaddress-%s" % interface_name : interface_mac,
        "ipaddress-%s" % interface_name  : ip,
        "netmask-%s" % interface_name    : netmask,
        "if_gateway-%s" % interface_name : interface_gateway,
        "static-%s" % interface_name     : 1,
    }, token)

    cobbler_api.modify_system(system_id, "name_servers", [interface_dns], token)

    cobbler_api.modify_system(system_id, "power_user", ipmi_username, token)
    cobbler_api.modify_system(system_id, "power_pass", ipmi_password, token)
    cobbler_api.modify_system(system_id, "power_address", ipmi_address, token)
    cobbler_api.modify_system(system_id, "power_type", "ipmilan", token)

    cobbler_api.save_system(system_id, token)

    return system_name


@clear_cached_systems
def update_system(system,
                  system_profile=None,
                  system_ks_file=None,

                  system_interface=None,
                  interface_name=None,
                  interface_cidr=None,
                  interface_mac=None,
                  interface_dns=None,
                  interface_gateway=None,

                  ipmi_username=None,
                  ipmi_password=None,
                  ipmi_address=None,):

    system_id = "system::%s" % system['name']

    cobbler_api = _find_cobbler_api(interface_cidr)
    if not cobbler_api:
        raise errors.InterfaceIPUnsupported(interface_cidr)

    token = _login(cobbler_api)

    try:
        ipa = IPNetwork(interface_cidr)
        ip = str(ipa.ip)
        netmask = str(ipa.netmask)

        d = {
            "ipaddress-%s" % interface_name: ip,
            "static-%s" % interface_name   : 1
        }
        if interface_mac:
            d[ "macaddress-%s" % interface_name ] = interface_mac
        if netmask:
            d[ "netmask-%s" % interface_name ] = netmask
            d[ "if_gateway-%s" % interface_name ] = interface_gateway

        cobbler_api.modify_system(system_id, "modify_interface", d, token)

        if interface_dns:
            cobbler_api.modify_system(system_id, "name_servers", [interface_dns], token)

        if system_profile:
            cobbler_api.modify_system(system_id, "profile", system_profile, token)
        if system_ks_file:
            cobbler_api.modify_system(system_id, "kickstart", system_ks_file, token)

        if ipmi_username:
            cobbler_api.modify_system(system_id, "power_user", ipmi_username, token)
        if ipmi_password:
            cobbler_api.modify_system(system_id, "power_pass", ipmi_password, token)
        if ipmi_address:
            cobbler_api.modify_system(system_id, "power_address", ipmi_address, token)

        cobbler_api.save_system(system_id, token)

    except:
        logger.debug('error while update_system, systen_name is: ' % system['name'])
        import traceback; traceback.print_exc();
        pass

    return system['name']


@clear_cached_systems
def remove_system(system_name):
    systems = get_all_systems()
    for system in systems:
        if system['name'] == system_name:
            logger.debug("found system: %s" % system_name)

            for cobbler_api in cobblers:
                token = _login(cobbler_api)
                try:
                    cobbler_api.remove_system(system_name, token)
                except:
                    logger.debug('error while remove_system, systen_name is: ' % system_name)
                    import traceback; traceback.print_exc();
                    pass

            return system_name

    return None


@clear_cached_systems
def rebuild_system(system_name, boot_mode):
    systems = get_all_systems()
    for system in systems:
        if system['name'] == system_name:
            # logger.debug("found system: %s" % system_name)
            system_id = "system::%s" % system['name']

            eth100 = system['interfaces']['eth100']
            cidr = eth100['ip_address'] + '/' + eth100['netmask']

            cobbler_api = _find_cobbler_api(cidr)
            if not cobbler_api:
                raise errors.InterfaceIPUnsupported(cidr)

            token = _login(cobbler_api)
            try:
                cobbler_api.modify_system(system_id, "netboot_enabled", True, token)
                cobbler_api.save_system(system_id, token)
            except:
                logger.debug('error while rebuild_system, systen_name is: ' % system_name)
                import traceback; traceback.print_exc();
                raise


            ipmi.boot_pxe(system, boot_mode)
            ipmi.power_reset(system)

            return system_name

    return None


def power_on_system(system_name):
    systems = get_all_systems()
    for system in systems:
        if system['name'] == system_name:
            logger.debug("found system: %s" % system_name)

            ipmi.power_on(system)

            return system

    return None


def power_off_system(system_name):
    systems = get_all_systems()
    for system in systems:
        if system['name'] == system_name:
            logger.debug("found system: %s" % system_name)

            ipmi.power_off(system)

            return system

    return None


def power_reset_system(system_name):
    systems = get_all_systems()
    for system in systems:
        if system['name'] == system_name:
            logger.debug("found system: %s" % system_name)

            ipmi.power_reset(system)

            return system

    return None


@clear_cached_systems
def sync():
    for cobbler_api in cobblers:
        try:
            token = _login(cobbler_api)
            cobbler_api.sync(token)
            time.sleep(2)
            # logger.info("syncing cobbler_api: %s" % cobbler_api)
        except:
            #logger.debug('error while cobbler_api.sync, cobbler_api is: ' % cobbler_api)
            import traceback; traceback.print_exc();
            raise


@clear_cached_systems
def find_dup():
    for network, cobbler_api in network_cobblers.items():
        systems = cobbler_api.get_systems()
        for system in systems:
            try:

                eth100 = system['interfaces']['eth100']
                cidr = eth100['ip_address'] + '/' + eth100['netmask']

                c = _find_cobbler_api(cidr)
                if c != cobbler_api:
                    logger.warn("in cobbler_api: %s, find system %s[%s]. it should be in %s" % (cobbler_api, system['name'], eth100['ip_address'], c))
                else:
                    pass
                    # logger.info("good, cobbler_api: %s, find correct system %s" % (cobbler_api, system['name']))
            except:
                logger.debug('system is: %s' % system)
                import traceback; traceback.print_exc();
                raise


@clear_cached_systems
def clear():
    pass


