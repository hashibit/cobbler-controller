import subprocess
from . import retry
from . import errors

from werkzeug.local import LocalProxy
from flask import current_app

logger = LocalProxy(lambda: current_app.logger)


@retry(3, 5)
def local_pipe(cmd):
    if type(cmd) is not list:
        cmd = cmd.split(" ")

    child = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    output = child.communicate()[0]
    retcode = child.returncode

    logger.info('return with rc=%d, output was:\n%s', retcode, output)

    if str(retcode) != "0":
        raise errors.IpmiCommandFailed(" ".join(cmd), retcode, output)

    return " ".join(cmd), retcode, output

def power_status(system):
    cmd = 'ipmitool -I lanplus -U %s -P %s -H %s power status' % (
            system['power_user'].strip(), system['power_pass'].strip(), system['power_address'].strip())
    logger.info(cmd)
    return local_pipe(cmd)


def power_reset(system):
    cmd = 'ipmitool -I lanplus -U %s -P %s -H %s power reset' % (
            system['power_user'].strip(), system['power_pass'].strip(), system['power_address'].strip())
    logger.info(cmd)
    return local_pipe(cmd)


def boot_pxe(system, boot_mode):
    if boot_mode is not None and boot_mode == 'legacy':
        cmd = 'ipmitool -I lanplus -U %s -P %s -H %s chassis bootdev pxe' % (
            system['power_user'].strip(), system['power_pass'].strip(), system['power_address'].strip())
    else:
        cmd = 'ipmitool -I lanplus -U %s -P %s -H %s chassis bootdev pxe options=persistent,efiboot ' % (
            system['power_user'].strip(), system['power_pass'].strip(), system['power_address'].strip())
    logger.info(cmd)
    return local_pipe(cmd)


def boot_bios(system):
    cmd = 'ipmitool -I lanplus -U %s -P %s -H %s chassis bootdev bios' % (
            system['power_user'].strip(), system['power_pass'].strip(), system['power_address'].strip())
    logger.info(cmd)
    return local_pipe(cmd)


