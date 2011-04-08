import logging
from Foundation import objc, NSObject, NSAutoreleasePool

log = logging.getLogger(__name__)

class MainThreadHelper(NSObject):
    def onMainThread(self):
        try:
            self.func()
        except:
            log.exception("Error in callback on mail thread")

def call_on_main_thread(callback, *args, **kwargs):
    pool = NSAutoreleasePool.new()

    obj = MainThreadHelper.new()
    obj.func = lambda: callback(*args, **kwargs)

    selector = objc.selector(obj.onMainThread, signature='v@:')
    later = obj.performSelectorOnMainThread_withObject_waitUntilDone_
    later(selector, None, False)
