import Queue
import threading
import logging
from collections import deque
import monocle

try:
    from async_cocoa import call_on_main_thread
except ImportError:
    def call_on_main_thread(callback, *args, **kwargs):
        raise NotImplementedError

log = logging.getLogger(__name__)

class AsyncJob(object):
    failure = None

    @monocle.o
    def start(self):
        try:
            yield self.do_stuff()
        except Exception, e:
            self.failure = e
            if hasattr(e, '_monocle'):
                log.error("%s\nMonocle-enhanced %s",
                          str(e), monocle.core.format_tb(e))
            else:
                log.exception(e)

    @monocle.o
    def do_stuff(self):
        pass

def worker_loop(in_queue, worker):
    while True:
        msg = in_queue.get()
        if msg is None:
            return
        try:
            callback, method, args, kwargs = msg
            result = getattr(worker, method)(*args, **kwargs)
            call_on_main_thread(callback, result)
        except Exception, e:
            monocle.core._add_monocle_tb(e)
            call_on_main_thread(callback, e)

class AsyncWorkerProxy(object):
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
    return AsyncWorkerProxy(in_queue, thread)

class SimpleWorkerManager(object):
    """
    A worker manager that allows at most one worker, and keeps a queue of
    clients waiting for a worker. Essentially this is a mutex: only one client
    can run at a time.
    """

    def __init__(self, create_worker, destroy_worker):
        self._create_worker = create_worker
        self._desotry_worker = destroy_worker
        self._worker_busy = None
        self._client_queue = deque()

    def get_worker(self):
        """
        Get a worker. This is called by o-routines and they expect a Callback
        in return.
        """
        cb = monocle.callback.Callback()
        self._client_queue.append(cb)
        self._dispatch_workers()
        return cb

    def _dispatch_workers(self):
        # Create new workers if we can. Actually, since we can only have one
        # worker, the logic is quite simple.
        if self._worker_busy:
            return

        if not self._client_queue:
            return

        self._worker_busy = True

        # the factory returns a callback; chain it to our client's result.
        create_worker_cb = self._create_worker()
        cb = self._client_queue.popleft()
        create_worker_cb.add(cb)

    def hand_back_worker(self, worker):
        """
        The client is done and no longer needs the worker.
        """
        destroy_worker_cb = self._desotry_worker(worker)
        self._worker_busy = False
        self._dispatch_workers()
        return destroy_worker_cb
