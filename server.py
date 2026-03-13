import signal

import gevent
from gevent.pool import Group

from gevent.pywsgi import WSGIServer
from app.app import app

http_server = WSGIServer(('', 5000), app)


def init_thread_groups():
    from app import thread_group
    from app.worker import sync_env, sync_cobbler

    t1 = gevent.spawn(sync_env)
    t2 = gevent.spawn(sync_cobbler)
    t3 = gevent.spawn(thread_group.monitor_forever)

    thread_group.manage(t1)
    thread_group.manage(t2)
    thread_group.manage(t3)


def init_logger():
    import logging
    from logging.handlers import RotatingFileHandler

    logger = logging.getLogger('infra_cobbler_hub')
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter("[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s")

    fh = RotatingFileHandler('/tmp/infra_cobbler_hub.log', maxBytes =1000000, backupCount=1)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    app.logger = logger


def stop():
    from app import thread_group

    http_server.stop()
    thread_group.kill_all()

gevent.signal(signal.SIGTERM, stop)
gevent.signal(signal.SIGQUIT, stop)
gevent.signal(signal.SIGINT, stop)


def start():
    try:
        http_server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        stop()


init_logger()
init_thread_groups()

start()

