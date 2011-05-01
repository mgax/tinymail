import logging
from Foundation import objc, NSObject, NSAutoreleasePool

log = logging.getLogger(__name__)

class MainThreadHelper(NSObject):
    def onMainThread(self):
        try:
            self.func()
        except:
            log.exception("Error in callback on mail thread")

def object_and_selector_for_callback(callback, *args, **kwargs):
    pool = NSAutoreleasePool.new()
    obj = MainThreadHelper.new()
    obj.func = lambda: callback(*args, **kwargs)
    selector = objc.selector(obj.onMainThread, signature='v@:')
    return obj, selector

def call_on_main_thread(callback, *args, **kwargs):
    obj, selector = object_and_selector_for_callback(callback, *args, **kwargs)
    obj_later = obj.performSelectorOnMainThread_withObject_waitUntilDone_
    obj_later(selector, None, False)
