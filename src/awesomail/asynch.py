import Queue
import threading
import logging
import monocle

log = logging.getLogger(__name__)

class AsynchJob(object):
    failure = None

    @monocle.o
    def start(self):
        try:
            yield self.do_stuff()
        except Exception, e:
            self.failure = e
            log.exception("Error in asynch job")

    @monocle.o
    def do_stuff(self):
        pass

def call_on_main_thread(callback, result):
    raise NotImplementedError

def worker_loop(in_queue, worker):
    while True:
        msg = in_queue.get()
        if msg is None:
            return
        callback, method, args, kwargs = msg
        result = getattr(worker, method)(*args, **kwargs)
        call_on_main_thread(callback, result)

class AsynchWorkerProxy(object):
    def __init__(self, in_queue, thread):
        self._in_queue = in_queue
        self._thread = thread

    def __getattr__(self, name):
        @monocle.o
        def method_proxy(*args, **kwargs):
            callback = monocle.callback.Callback()
            self._in_queue.put((callback, name, args, kwargs))
            return callback
        return method_proxy

    def done(self):
        self._in_queue.put(None)
        self._thread.join()

def start_worker(worker):
    in_queue = Queue.Queue()
    thread = threading.Thread(target=worker_loop, args=(in_queue, worker))
    thread.start()
    return AsynchWorkerProxy(in_queue, thread)
