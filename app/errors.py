

class InterfaceIPUnsupported(Exception):

    def __init__(self, ip):
        self.ip = ip

    def __str__(self):
        return "network interface ip not supported. current only support 10.9.240.* 10.9.242.* or 172.20.25.* or 172.20.26.* "

class IpmiCommandFailed(Exception):

    def __init__(self, cmd, retcode, output):
        self.cmd = cmd
        self.retcode = retcode
        self.output = output

    def __str__(self):
        return "Invoke ipmitool failed: cmd[%s], retcode[%s], output[%s]" % (self.cmd, self.retcode, self.output)

