import nose

class TinymailTestPlugin(nose.plugins.Plugin):
    def configure(self, options, config):
        self.enabled = True

    def prepareTestCase(self, testCase):
        def run_the_test(result):
            call_on_main_thread(async_testcase_run, testCase.test, result)
        return run_the_test

from threading import Thread, Semaphore
import logging
from functools import wraps

from PyObjCTools import AppHelper
from monocle import _o, launch
from monocle.core import Callback
import monocle

log = logging.getLogger(__name__)

def maybe_callback(result):
    # TODO before calling the method, check if it's an o-routine; if so,
    # expect a callback, and set a timeout. otherwise, don't expect a
    # callback, and crash if we get one.
    if isinstance(result, Callback):
        return result
    else:
        cb = Callback()
        cb(result)
        return cb

@_o
def async_testcase_run(testcase, result):
    if result is None: result = testcase.defaultTestResult()
    result.startTest(testcase)
    testMethod = getattr(testcase, testcase._testMethodName)
    try:
        try:
            yield maybe_callback(testcase.setUp())
        except KeyboardInterrupt:
            raise
        except:
            result.addError(testcase, testcase._exc_info())
            return

        ok = False
        try:
            yield maybe_callback(testMethod())
            ok = True
        except testcase.failureException:
            result.addFailure(testcase, testcase._exc_info())
        except KeyboardInterrupt:
            raise
        except:
            result.addError(testcase, testcase._exc_info())

        try:
            yield maybe_callback(testcase.tearDown())
        except KeyboardInterrupt:
            raise
        except:
            result.addError(testcase, testcase._exc_info())
            ok = False
        if ok: result.addSuccess(testcase)
    finally:
        result.stopTest(testcase)

def call_on_main_thread(func, *args, **kwargs):
    done = Semaphore(0)
    # TODO use other name than "result"
    result = []

    def wrapped_call():
        try:
            res_cb = func(*args, **kwargs)
        except Exception, e:
            res_cb = Callback()
            res_cb(e)

        if not isinstance(res_cb, Callback):
            raise ValueError("Expected a monocle Callback from %r, got %r" %
                             (func, res_cb))

        @_o
        def wait_for_result():
            try:
                res = yield res_cb
            except Exception, e:
                # TODO print traceback to a StringIO?
                res = e

            result.append(res)
            done.release()

        wait_for_result()

    AppHelper.callAfter(wrapped_call)
    done.acquire()
    if isinstance(result[0], Exception):
        raise result[0]
    else:
        return result[0]

def runs_on_main_thread(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return call_on_main_thread(monocle.o(func), *args, **kwargs)
    return wrapper

nose_threaded = False

def run_nose(nose_done):
    global nose_threaded
    nose_threaded = True
    try:
        import nose
        try:
            import logging; logging.getLogger().handlers[0].level = 99
            nose.main(addplugins=[TinymailTestPlugin()])
        except SystemExit:
            pass
    except:
        log.exception('Uncaught exception in nose thread')
    finally:
        AppHelper.callAfter(nose_done, None)

@_o
def main_o():
    try:
        nose_done = Callback()
        nose_thread = Thread(target=run_nose, args=(nose_done,))
        nose_thread.start()
        yield nose_done
        nose_thread.join()
    except:
        # TODO: need handler for this exception
        log.exception('Uncaught exception in main loop')
