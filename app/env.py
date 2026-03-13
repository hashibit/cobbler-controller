import os
import logging

import subprocess
import gevent
import git
from flask import copy_current_request_context
from flask import current_app

from urllib.parse import quote

from .deploy import Cluster, Deployment

from . import thread_group

default_git_username = "rainy-robot"
default_git_password = "uayaeCh8"

try:
    git_username = quote(os.environ['GIT_USERNAME'])
    git_password = quote(os.environ['GIT_PASSWORD'])
except:
    git_username = quote(default_git_username)
    git_password = quote(default_git_password)

envs_git_repo = "http://%s:%s@gitlab.sz.sensetime.com/rainy/infra/env.git" % (git_username, git_password)


curr_dir = os.path.dirname(os.path.abspath(__file__))
envs_dir = os.path.join(curr_dir, os.pardir, "vendor", "infra-envs")

print(envs_dir)

from gevent.lock import BoundedSemaphore
sem = BoundedSemaphore(1)

def sync_envs():
    with sem:
        if os.path.isdir(envs_dir):
            repo = git.Repo(envs_dir)
        else:
            repo = git.Repo.clone_from(envs_git_repo, envs_dir, branch='master')

        repo.heads.master.checkout(force=True)
        origin = repo.remote('origin')
        origin.pull()


def get_all_envs():
    return [name for name in os.listdir(envs_dir)]


def get_env(env_name):
    env_files = {
        'inventory': '',
        'group_vars':{
            'all.yml': ''
        },
        'license-ca': {
            'config': {
                'config.yml': ''
             },
            'binary': '',
        }
    }
    path = os.path.join(envs_dir, env_name)
    if not os.path.isdir(path):
        return None

    path_inventory = os.path.join(envs_dir, env_name, 'inventory')
    path_all_yml = os.path.join(envs_dir, env_name, 'group_vars', 'all.yml')
    path_license = os.path.join(envs_dir, env_name, 'license-ca')
    path_license_config = os.path.join(envs_dir, env_name, 'license-ca', 'config', 'config.yml')

    if os.path.isfile(path_inventory):
        with open(path_inventory, 'r') as f:
            env_files['inventory'] = f.read()

    if os.path.isfile(path_all_yml):
        with open(path_all_yml, 'r') as f:
            env_files['group_vars']['all.yml'] = f.read()

    if os.path.isfile(path_license_config):
        with open(path_license_config, 'r') as f:
            env_files['license-ca']['config']['config.yml'] = f.read()

    # eg. license-ca.v1.1.0
    for filename in os.listdir(path_license):
        if filename.startswith('license-ca'):
            env_files['license-ca']['binary'] = filename

    return env_files


def deploy_env(env_name, infra_version, registry_version, yum_version, receivers="",is_rebuild=True,product="su"):

    def config_logger(env_name, log_file):
        logger = logging.getLogger('hub-deploy-%s' % env_name)
        logger.setLevel(logging.DEBUG)

        if logger.hasHandlers():
            return logger

        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)

        formatter = logging.Formatter("[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s")
        fh.setFormatter(formatter)

        logger.addHandler(fh)

        return logger

    logger_file = "/tmp/hub-deploy.%s.log" % env_name
    logger = config_logger(env_name, logger_file)

    cluster = Cluster(env_name, logger)

    env_files = get_env(env_name)
    if env_files is None:
        raise Exception("env[%s] is not found." % env_name)

    cluster.load_nodes(env_files['inventory'])
    d = Deployment(cluster, logger)

    if is_rebuild:
        d.rebuild()

    @copy_current_request_context
    def deploy_job():
        gevent.sleep(10)
        try:
            d.deploy(infra_version, registry_version, yum_version, git_username, git_password, receivers, product)
        except Exception as e:
            print("exception happended in d.deploy, error: %s" % str(e))
            pass

    t = gevent.spawn(deploy_job)
    t_name = "deploy-thread-%s" % env_name
    t.name = t_name

    thread_group.manage(t, t_name)

    current_app.logger.info("deploy log file %s" % logger_file)

    return logger_file


def deploy_env_log(env_name):
    import re

    logger_file = "/tmp/hub-deploy.%s.log" % env_name
    p = subprocess.Popen(["tail", logger_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    lines = p.communicate()[0]
    lines = lines.decode('utf-8')
    lines = re.split('\t|\n|,', lines)
    lines = [l for l in lines if len(l) > 0]
    return lines


def sync():
    sync_envs()
