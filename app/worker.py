import gevent

from . import env
from . import cobbler

def sync_env():
    while True:
        try:
            env.sync()
        except:
            pass
        gevent.sleep(5)

def sync_cobbler():
    while True:
        try:
            cobbler.sync()
        except:
            pass
        gevent.sleep(60)

