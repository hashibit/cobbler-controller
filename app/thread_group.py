import time
import gevent
from gevent.pool import Group

group = Group()

threads_name_dict = {}

def _get_current_logger():
    from app.app import app
    return app.logger

def manage(t, name=None):
    if name is None:
        name = t.name

    logger = _get_current_logger()
    logger.debug('manage thread: %s, name: %s' % (t, name))
    exist = threads_name_dict.get(name)
    if exist:
        logger.debug('the thread is already exist, kill it.')
        # block until success killed.
        group.killone(exist)

    group.add(t)
    threads_name_dict[name] = t


def unmanage(t, name=None):
    if name is None:
        name = t.name

    logger = _get_current_logger()
    logger.debug('unmanage thread: %s, name: %s' % (t, name))

    group.discard(t)
    thread_dicts[name] = None


def kill_all():
    logger = _get_current_logger()
    logger.debug('kill all threads, empty threads_name_dicts')

    group.kill()
    threads_name_dict = {}


def monitor():
    runnings = sorted([str(g) for g in group.greenlets])
    dyings = sorted([str(g) for g in group.dying])

    return {
        "runnings:": runnings,
        "dyings:": dyings
    }


def monitor_forever():
    import json
    logger = _get_current_logger()

    while True:
        m = monitor()
        # logger.debug(json.dumps(m, indent=4))
        time.sleep(5)

