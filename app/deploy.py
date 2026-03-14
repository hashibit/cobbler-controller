import os
import shutil
import sys
import subprocess
import re
import logging
import time
import gevent
import datetime


from . import cobbler

curr_dir = os.path.dirname(os.path.abspath(__file__))
scripts_path = os.path.join(curr_dir, os.pardir, "scripts")

infra_repo_location = "http://sz.rainy.mysecurity.net/config/infra.repo"
tmux_conf_location = "http://sz.rainy.mysecurity.net/config/tmux.conf"
pip_conf_location = "http://sz.rainy.mysecurity.net/config/pip.conf"
yum_conf_location = "http://sz.rainy.mysecurity.net/config/yum.conf"
bat_bin_location = "http://sz.rainy.mysecurity.net/config/bat"
fd_bin_location = "http://sz.rainy.mysecurity.net/config/fd"
kubetail_bin_location = "http://sz.rainy.mysecurity.net/config/kubetail"
kube_prompt_bin_location = "http://sz.rainy.mysecurity.net/config/kube-prompt"

default_logger = logging.getLogger("deploy")


class SSHTunnel(object):

    def __init__(self, remote, password="V1p3r1@#$%", logger=default_logger):
        self.logger = logger

        self.remote = remote
        self.password = password
        self.sshpass = ["sshpass", "-p", "%s" % password]

    def execute(self, args):
        self.logger.debug("#=> %s" % " ".join(args))

        ssh1 = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        try:
            outs, errs = ssh1.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            self.logger.error("#==> subprocess.TimeoutExpired, retry")
            ssh1.kill()
            outs, errs = ssh1.communicate()
        except Exception as e:
            import traceback

            stack = traceback.format_exc()
            self.logger.error("#==> %s" % stack)

        self.last_returncode = ssh1.returncode

        self.logger.debug(
            "#==> stdout: %s, stderr: %s, rc: %s" % (outs, errs, ssh1.returncode)
        )
        return outs.split("\n"), errs.split("\n")


class SCPPipe(SSHTunnel):

    def execute(self, local_filepath, remote_filepath):
        opts = [
            "scp",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            local_filepath,
            "root@%s:%s" % (self.remote, remote_filepath),
        ]
        args = self.sshpass + opts

        return super().execute(args)


class SSHPipe(SSHTunnel):

    def execute(self, cmd):
        if type(cmd) is not list:
            cmd = cmd.split(" ")

        opts = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "root@%s" % self.remote,
        ]
        args = self.sshpass + opts + cmd

        return super().execute(args)


class Cluster:
    def __init__(self, name, logger=default_logger):
        self.name = name
        self.logger = logger

        self.nodes = {}

    def load_nodes(self, inventory_file):
        self._parse_inventory(inventory_file.split("\n"))

    def _parse_inventory(self, lines):
        inventory_parser = InventoryParser()
        inventory_parser.parse(lines)

        is_first_node = True
        for host in inventory_parser.iter_hosts():
            node = Node()
            try:
                node.from_inventory(host)
                self.nodes[node.name] = node

                # FIXME assume the first node as controller node.
                if is_first_node:
                    self.controller_node = node
                    is_first_node = False

            except:
                self.logger.info("cannot parse inventory host: %s, skip." % host)

    def teardown(self):
        self.logger.info("going to teardown the whole cluster...")
        self.print_nodes()
        confirm = True

        if confirm:
            founded_systems = []
            for name, node in self.nodes.items():
                self.logger.info("\tfinding system in cobber...")
                system = cobbler.get_system(system_ip=node.ip)
                if system:
                    founded_systems.append(system)
                else:
                    self.logger.error(
                        "\tsystem for ip(%s) not find in cobber. be carefull!!! now exit program. :("
                        % node.ip
                    )
                    sys.exit(1)

            self.logger.info("found systems in cobber for every node")

            for system in founded_systems:
                self.logger.info("\tgoing to rebuild %s..." % system["name"])
                cobbler.rebuild_system(system["name"], "legacy")

        else:
            self.logger.info(
                "wise choice! I dare not to teardown cluster either. Exit."
            )
            sys.exit(0)

    def print_nodes(self):
        self.logger.info("cluster %s has the following nodes:" % self.name)
        for name, node in self.nodes.items():
            self.logger.info("\t%s" % node)

    def print_nodes_status(self):
        ready, downs = self.check_nodes_up()
        if ready:
            self.logger.info("good news! all nodes are up!")
        else:
            self.logger.info("some nodes %s are still down." % downs)

    def check_nodes_up(self):
        ups = []
        downs = []
        for name, node in self.nodes.items():
            if self.check_node_up(node):
                ups.append(node)
            else:
                downs.append(node)

        if downs:
            return False, downs
        else:
            return True, []

    def check_node_up(self, node):
        self.logger.info("checking node [%s] status..." % node.ip)

        nc = "nc %s 22" % node.ip
        pipe = subprocess.Popen(
            nc.split(" "),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        try:
            outs, errs = pipe.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            pipe.kill()
            outs, errs = pipe.communicate()

        status = pipe.returncode == 0
        self.logger.info("node is %s." % ("up" if status else "still down"))

        return status

    def status(self):
        self.print_nodes()
        self.check_nodes_up()
        self.logger.info("\n")


class Node(object):
    def __init__(self):
        self.name = None
        self.ip = None
        self.ssh_username = None
        self.ssh_password = None

    def from_inventory(self, inventory_node):
        self.name = inventory_node.name
        self.ip = inventory_node.variables["ansible_host"]
        self.ssh_username = inventory_node.variables["ansible_user"]
        self.ssh_password = inventory_node.variables["ansible_ssh_pass"]

    def __repr__(self):
        return "name: %s, ip: %s, username: %s, password: %s" % (
            self.name,
            self.ip,
            self.ssh_username,
            self.ssh_password,
        )


class InventoryParser(object):

    def __init__(self):
        self.nodes = {}

    def node_with_name(self, name):
        node = self.nodes.get(name)
        if node is None:
            node = InventoryNode(name)
            self.nodes[name] = node
        return node

    def parse(self, inventory_lines):
        lines = (line.rstrip() for line in inventory_lines)

        current_group = None
        section_type = None

        for line in lines:

            if line.strip()[:1] in ["", "#"]:
                # Empty line or comment, ignore.
                continue

            if line.startswith("[") and line.endswith("]"):
                # Start of group block. Make the group node the current node
                # and record the group's section type (if any) so we know how
                # to parse a normal line.
                name, _, section_type = line[1:-1].partition(":")
                node = self.node_with_name(name)
                current_group = node

            elif line.startswith("["):
                raise Exception("Syntax error: %s" % line)

            elif section_type == "vars":
                # Line in a vars section.
                name, val = line.split("=", 1)
                current_group.add_variables({name: val})

            else:
                # Line containing a host or group name
                if " " in line:
                    name, variables = line.split(" ", 1)
                    variables = dict(i.split("=", 1) for i in variables.split())
                else:
                    name, variables = line, {}

                name, _, port = name.partition(":")
                if port:
                    variables["__port__"] = port

                node = self.node_with_name(name)
                node.add_variables(variables)

                if current_group:
                    current_group.add_child(node)
                    node.add_parent(current_group)
                else:
                    ungrouped = self.node_with_name("ungrouped")
                    ungrouped.add_child(node)
                    node.add_parent(ungrouped)

    def iter_hosts(self):
        for node in self.nodes.values():
            if node.is_host():
                yield node

    def iter_groups(self):
        for node in self.nodes.values():
            if not node.is_host():
                yield node


class InventoryNode(object):

    def __init__(self, name):
        self.name = name
        self.variables = {}
        self.children = {}
        self.parents = {}

    def add_variables(self, variables):
        self.variables.update(variables)

    def add_child(self, node):
        self.children[node.name] = node

    def add_parent(self, node):
        self.parents[node.name] = node

    def is_host(self):
        return len(self.children) == 0 and ("ansible_host" in self.variables)

    def __unicode__(self):
        return self.__repr__()

    def __repr__(self):
        return "%s %r children=%r parents=%r" % (
            self.name,
            self.variables,
            list(self.children),
            list(self.parents),
        )


class Deployment(object):

    deploy_folder = "/data/awesome"
    deploy_script = "rainy-deploy.sh"

    def __init__(self, cluster, logger=default_logger):
        self.cluster = cluster
        self.logger = logger

        self.controller_sshpipe = SSHPipe(
            cluster.controller_node.ip, logger=self.logger
        )
        self.controller_scppipe = SCPPipe(
            cluster.controller_node.ip, logger=self.logger
        )

    def step_teardown_nodes(self):
        self.cluster.teardown()

    def step_poll_node_up(self):
        downs = list(self.cluster.nodes.values())
        while downs:
            ready, downs = self.cluster.check_nodes_up()
            if ready:
                self.logger.info("good news! all nodes are up!")
                break
            else:
                self.logger.info(
                    "some nodes %s are still down. waiting for them..."
                    % ([node.ip for node in downs])
                )
                gevent.sleep(3)

    def step_clean_nodes_disks(self):
        for name, node in self.cluster.nodes.items():
            node_sshpipe = SSHPipe(node.ip, logger=self.logger)
            outs, errs = node_sshpipe.execute("lsblk -n -d -o NAME,MOUNTPOINT")

            outs = [line.strip() for line in outs]
            outs = [
                line for line in outs if "sda" not in line and " " not in line and line
            ]

            disks = ["/dev/" + line for line in outs]
            self.logger.info(
                "node %s has the following disks. clean their partitions..." % node.ip
            )
            self.logger.info(disks)

            if True:
                for disk in disks:
                    self.logger.info("cleaning disk %s." % disk)
                    node_sshpipe.execute("dd if=/dev/zero of=%s bs=1M count=1" % disk)
            else:
                self.logger.info("skip clean disks for node %s..." % node.ip)
                continue

    def step_deploy_rainy(
        self,
        infra_version,
        registry_version,
        yum_version,
        git_username,
        git_password,
        receivers,
        product,
    ):
        self.logger.info("start deploy rainy.")

        local_filepath = os.path.join(scripts_path, self.deploy_script)
        remote_filepath = os.path.join(self.deploy_folder, self.deploy_script)

        self.controller_sshpipe.execute("mkdir -p %s" % self.deploy_folder)
        self.controller_scppipe.execute(local_filepath, remote_filepath)

        # prepare infra repo. in case we are using online yum
        self.controller_sshpipe.execute("rm -rf /etc/yum.repos.d/*.repo")
        self.controller_sshpipe.execute(
            "curl -o /etc/yum.repos.d/infra.repo %s" % infra_repo_location
        )
        self.controller_sshpipe.execute(
            "curl -o /root/.tmux.conf %s" % tmux_conf_location
        )
        self.controller_sshpipe.execute("curl -o /etc/yum.conf %s" % yum_conf_location)

        self.controller_sshpipe.execute(
            "curl -o /usr/bin/bat %s; chmod +x /usr/bin/bat;" % bat_bin_location
        )
        self.controller_sshpipe.execute(
            "curl -o /usr/bin/fd %s; chmod +x /usr/bin/fd;" % fd_bin_location
        )
        self.controller_sshpipe.execute(
            "curl -o /usr/bin/kubetail %s; chmod +x /usr/bin/kubetail;"
            % kubetail_bin_location
        )
        self.controller_sshpipe.execute(
            "curl -o /usr/bin/kube-prompt %s; chmod +x /usr/bin/kube-prompt;"
            % kube_prompt_bin_location
        )

        self.controller_sshpipe.execute("yum clean all")
        self.controller_sshpipe.execute("rm -rf /var/lib/cache")
        self.controller_sshpipe.execute("yum makecache")

        self.controller_sshpipe.execute("mkdir -p /root/.pip")
        self.controller_sshpipe.execute(
            "curl -o /root/.pip/pip.conf %s" % pip_conf_location
        )

        self.controller_sshpipe.execute("yum install -y tmux")
        self.controller_sshpipe.execute("tmux new-session -d -s rainy-deploy")
        self.controller_sshpipe.execute("chmod +x %s" % remote_filepath)

        receivers_param = ' --receivers "%s" ' % receivers if receivers else ""
        remote_cmd = (
            " GIT_USERNAME=%s GIT_PASSWORD=%s %s --env %s --infra %s --registry %s --yum %s --product %s %s default |tee -a /tmp/rainy-deploy.log "
            % (
                git_username,
                git_password,
                remote_filepath,
                self.cluster.name,
                infra_version,
                registry_version,
                yum_version,
                product,
                receivers_param,
            )
        )

        self.controller_sshpipe.execute(
            "tmux send -t rainy-deploy '%s' ENTER" % remote_cmd
        )

        self.logger.info(
            "rainy-deploy.sh is executing in remote host[%s]. you can login that host and use `tmux a` to see future process."
            % self.controller_sshpipe.remote
        )
        now = datetime.datetime.now()
        self.logger.info("finished. \n\n\n\n")

    def deploy(
        self,
        infra_version,
        registry_version,
        yum_version,
        git_username,
        git_password,
        receivers="",
        product="su",
    ):
        now = datetime.datetime.now()
        self.logger.info("started.")

        try:
            self.step_poll_node_up()
            self.step_clean_nodes_disks()

            self.step_deploy_rainy(
                infra_version,
                registry_version,
                yum_version,
                git_username,
                git_password,
                receivers,
                product,
            )
        except Exception as e:
            self.logger.error(
                "cannot deploy %s, error is: %s" % (self.cluster.name, str(e))
            )

    def rebuild(self):
        self.step_teardown_nodes()
