import time


def retry(num, wait):
    def deco(func):
        def inner(*args, **kwargs):
            for i in range(0, num):
                try:
                    ret = func(*args, **kwargs)
                except Exception as e:
                    # this is last try
                    if i == num - 1:
                        print("function failed %d times, total fail." % (num))
                        raise e
                    else:
                        print("function failed with err: %s, sleep %d seconds and retry again." % (str(e), wait))
                        time.sleep(wait)
                else:
                    return ret

        return inner
    return deco
