import datetime

from gevent import monkey
monkey.patch_all()

from flask import Flask
from flask import request, Response

from flask_json import FlaskJSON, JsonError, json_response, as_json
from flask_jwt import JWT, jwt_required, current_identity

from . import cobbler
from . import user
from . import env
from . import thread_group


app = Flask(__name__)
app.config['SECRET_KEY'] = 'a-secre1-t0ken'
app.config['JWT_EXPIRATION_DELTA'] = datetime.timedelta(seconds=60*60*6)
app.config['JWT_AUTH_HEADER_PREFIX'] = "Bearer"

json = FlaskJSON()
json.init_app(app)

jwt = JWT(app, user.authenticate, user.identity)


@app.route("/")
def index():
    return "welcome to cobbler hub."

@app.route("/systems", methods=['POST', 'GET'])
@as_json
@jwt_required()
def cobbler_systems():
    if request.method == 'POST':
        params = request.get_json(force=True)

        system_name = params['name']
        system_profile = params.get('profile', cobbler.default_profile)
        system_ks_file = params.get('ks', cobbler.default_ks_file)

        system_interface = params['network_if']
        interface_name = system_interface['name']
        interface_cidr = system_interface['cidr']
        interface_mac = system_interface['mac']
        interface_dns = system_interface['dns']
        interface_gateway = system_interface['gateway']

        system_ipmi = params['ipmi']
        ipmi_username = system_ipmi['username']
        ipmi_password = system_ipmi['password']
        ipmi_address = system_ipmi['address']

        ret = cobbler.create_system(system_name,
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
                                    ipmi_address)

        return ret

    else:
        systems = cobbler.get_all_systems()
        return systems


@app.route("/systems/<name>", methods=['POST', 'GET', 'DELETE'])
@as_json
@jwt_required()
def cobbler_system(name):
    system = cobbler.get_system(system_name=name)
    if system is None:
        return json_response(404, text='not found')

    if request.method == 'POST':
        params = request.get_json(force=True)

        system_profile = params.get('profile', None)
        system_ks_file = params.get('ks', None)

        system_interface = params.get('network_if', {})
        interface_name = system_interface.get('name', None)
        interface_cidr = system_interface.get('cidr', None)
        interface_mac = system_interface.get('mac', None)
        interface_dns = system_interface.get('dns', None)
        interface_gateway = system_interface.get('gateway', None)

        system_ipmi = params.get('ipmi', {})
        ipmi_username = system_ipmi.get('username', None)
        ipmi_password = system_ipmi.get('password', None)
        ipmi_address = system_ipmi.get('address', None)

        ret = cobbler.update_system(system,
                                    system_profile=system_profile,
                                    system_ks_file=system_ks_file,
                                    system_interface=system_interface,
                                    interface_name=interface_name,
                                    interface_cidr=interface_cidr,
                                    interface_mac=interface_mac,
                                    interface_dns=interface_dns,
                                    interface_gateway=interface_gateway,
                                    ipmi_username=ipmi_username,
                                    ipmi_password=ipmi_password,
                                    ipmi_address=ipmi_address)

        return cobbler.get_system(system_name=name)

    elif request.method == 'GET':
        return system

    else:
        # delete system
        return cobbler.remove_system(name)


@app.route("/systems/ip/<ip>", methods=['GET'])
@as_json
@jwt_required()
def cobbler_system_by_ip(ip):
    system = cobbler.get_system(system_ip=ip)
    if system is None:
        return json_response(404, text='not found')

    return system


@app.route("/systems/<name>/rebuild", methods=['POST'])
@as_json
@jwt_required()
def cobbler_system_rebuild(name):
    params = request.get_json(force=True)

    boot_mode = params.get('boot_mode', None)
    system = cobbler.rebuild_system(name,boot_mode)
    if system is None:
        return json_response(404, text='not found.')

    return system


@app.route("/systems/<name>/power_off", methods=['POST'])
@as_json
@jwt_required()
def cobbler_system_power_off(name):
    system = cobbler.power_off_system(name)
    if system is None:
        return json_response(404, text='not found.')

    return system


@app.route("/systems/<name>/power_on", methods=['POST'])
@as_json
@jwt_required()
def cobbler_system_power_on(name):
    system = cobbler.power_on_system(name)
    if system is None:
        return json_response(404, text='not found.')

    return system


@app.route("/systems/<name>/power_reset", methods=['POST'])
@as_json
@jwt_required()
def cobbler_system_power_reset(name):
    system = cobbler.power_reset_system(name)
    if system is None:
        return json_response(404, text='not found.')

    return system


@app.route("/admin/systems/sync", methods=['POST'])
@as_json
@jwt_required()
def cobbler_sync():
    cobbler.sync()
    return {}


@app.route("/admin/systems/find_dup", methods=['POST'])
@as_json
@jwt_required()
def cobbler_find_dup():
    cobbler.find_dup()
    return {}


@app.route("/admin/systems/clear_cache", methods=['POST'])
@as_json
@jwt_required()
def cobbler_clear():
    cobbler.clear()
    return {}


@app.route("/envs", methods=['GET'])
@as_json
@jwt_required()
def infra_envs():
    envs = env.get_all_envs()
    return envs


@app.route("/envs/<name>", methods=['GET'])
@as_json
@jwt_required()
def infra_env(name):
    return env.get_env(name)


@app.route("/envs/<name>/deploy", methods=['POST'])
@as_json
@jwt_required()
def infra_env_deploy(name):
    params = request.get_json(force=True)

    infra_version = params.get('infra_version', None)
    registry_version = params.get('registry_version', None)
    yum_version = params.get('yum_version', None)
    receivers = params.get('receivers', "")
    is_rebuild = params.get('is_rebuild', True)
    product = params.get('product', "su")
    if not infra_version or not registry_version or not yum_version:
        return json_response(400, text='bad request: infra_version and registry_version and yum_version must be submit.')

    try:
        logger_file = env.deploy_env(name, infra_version, registry_version, yum_version, receivers, is_rebuild, product)

        return {
            "message": "job deploy %s submitted. use ' curl http://10.9.242.6:5000/envs/%s/deploy/log ' to stream deploy log" % (name, name)
        }
    except Exception as e:
        import traceback
        stack = traceback.format_exc()
        return {
            "message": "this request failed. retry later. error: %s, stack: %s" % (str(e), stack)
        }


@app.route("/envs/<name>/deploy/log", methods=['GET'])
@as_json
def infra_env_deploy_log(name):
    logs = env.deploy_env_log(name)
    return {'messages': logs}


@app.route("/envs/sync", methods=['POST'])
@as_json
@jwt_required()
def infra_envs_sync():
    env.sync()
    return {}


@app.route("/threads_monitor", methods=['GET'])
@as_json
@jwt_required()
def infra_monitor_greenlets():
    return thread_group.monitor()
