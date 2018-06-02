__author__ = 'zbig'

import signal
import socket

"""
usage examples:

    ## to dynamically set timeout based on configuratin parameters use decorators factory:

    def get_dynamically_decorated_functions_factory_class(self, timeout_time_sec=1.0):
        timeout_int = int(timeout_time_sec)

        class DecoratedFunctions(object):
            @decorators.timeout(timeout_int)
            def do_sleep(self, sleep_time_sec):
                time.sleep(sleep_time_sec)

            @decorators.socket_timeout(timeout_time_sec)
            def get_http_data(self, url_address):
                return urllib2.urlopen(url_address)

        return DecoratedFunctions
"""


class TimeoutError(Exception):
    def __init__(self, value = "Timed Out"):
        self.value = value

    def __str__(self):
        return repr(self.value)


def timeout(seconds_before_timeout):  # this works only on posix
    def decorate(f):
        def handler(signum, frame):
            raise TimeoutError()

        def new_f(*args, **kwargs):
            old = signal.signal(signal.SIGALRM, handler)
            signal.alarm(seconds_before_timeout)
            try:
                result = f(*args, **kwargs)
            finally:
                signal.signal(signal.SIGALRM, old)
            signal.alarm(0)
            return result
        new_f.func_name = f.func_name
        return new_f
    return decorate


def socket_timeout(seconds_before_timeout):
    def decorate(f):
        def new_f(*args, **kwargs):

            original_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(seconds_before_timeout)

            try:
                result = f(*args, **kwargs)
            finally:
                socket.setdefaulttimeout(original_timeout)

            return result
        new_f.func_name = f.func_name
        return new_f
    return decorate


