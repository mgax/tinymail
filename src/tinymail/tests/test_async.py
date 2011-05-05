import unittest2 as unittest
import monocle
from mock import Mock, patch

@monocle.o
def add_one(value):
    yield monocle.Return(value + 1)

class AsyncJobTest(unittest.TestCase):
    def test_simple_job(self):
        out = {}
        from tinymail.async import AsyncJob
        class MyJob(AsyncJob):
            @monocle.o
            def do_stuff(self):
                out['result'] = yield add_one(12)

        MyJob().start()

        self.assertEqual(out, {'result': 13})

    def test_exception_in_job(self):
        from tinymail.async import AsyncJob
        class MyJob(AsyncJob):
            @monocle.o
            def do_stuff(self):
                raise ValueError('ha!')

        job = MyJob()
        job.start()
        self.assertTrue(isinstance(job.failure, ValueError))
        self.assertEqual(job.failure.args, ('ha!',))

class AsyncWorkerTest(unittest.TestCase):
    def setUp(self):
        from tinymail import async
        self._patch = patch.object(async, 'call_on_main_thread')
        m = self._patch.start()
        m.side_effect = lambda callback, result: callback(result)

    def tearDown(self):
        self._patch.stop()

    def test_input_queue(self):
        called = []
        from tinymail.async import start_worker
        class MyWorker(object):
            def plus(self, a, b):
                called.append((a,b))

        try:
            worker = start_worker(MyWorker())
            d = worker.plus(3, 4)
        finally:
            worker.done()

        self.assertEqual(called, [(3, 4)])

    def test_return_value(self):
        from tinymail.async import start_worker
        class MyWorker(object):
            def get_13(self):
                return 13

        try:
            worker = start_worker(MyWorker())
            d = worker.get_13()
        finally:
            worker.done()

        self.assertEqual(d.result, 13)

    def test_exception(self):
        from tinymail.async import start_worker
        class MyWorker(object):
            def freak_out(self):
                raise ValueError('hi')

        try:
            worker = start_worker(MyWorker())
            d = worker.freak_out()
        finally:
            worker.done()

        self.assertTrue(isinstance(d.result, ValueError))
        self.assertEqual(d.result.args, ('hi',))

class SimpleWorkerManagerTest(unittest.TestCase):
    def setUp(self):
        from tinymail.async import SimpleWorkerManager
        self.create_worker = Mock()
        self.destroy_worker = Mock()
        self.wm = SimpleWorkerManager(self.create_worker, self.destroy_worker)

    def test_get_one_worker(self):
        worker = object()
        self.create_worker.return_value = monocle.callback.defer(worker)
        results = []
        self.wm.get_worker().add(results.append)

        self.assertEqual(results, [worker])

    def test_worker_factory_delayed(self):
        self.create_worker.return_value = monocle.callback.Callback()
        worker_cb = self.wm.get_worker()
        results = []
        worker_cb.add(results.append)

        # worker not ready, we should have received nothing
        self.assertEqual(results, [])

        worker = object()
        create_worker_cb = self.create_worker.return_value
        create_worker_cb(worker)

        # worker ready, we should have received it
        self.assertEqual(results, [worker])

    def test_worker_done(self):
        self.create_worker.return_value = monocle.callback.defer(object())
        results = []
        self.wm.get_worker().add(results.append)
        worker = results[0]

        self.wm.hand_back_worker(worker)

        self.destroy_worker.assert_called_once_with(worker)

    def test_request_sequence(self):
        self.create_worker.return_value = monocle.callback.defer(object())
        results = []
        self.wm.get_worker().add(results.append)
        worker = results[0]
        self.wm.hand_back_worker(worker)

        worker2 = object()
        self.create_worker.return_value = monocle.callback.defer(worker2)
        results2 = []
        self.wm.get_worker().add(results2.append)

        self.assertIs(results2[0], worker2)

    def test_request_queue(self):
        results1 = []; worker1 = object()
        results2 = []; worker2 = object()
        self.create_worker.return_value = monocle.callback.defer(worker1)
        self.wm.get_worker().add(results1.append)
        self.wm.get_worker().add(results2.append)

        self.assertEqual(results1, [worker1])
        self.assertEqual(results2, [])

        self.create_worker.return_value = monocle.callback.defer(worker2)
        self.wm.hand_back_worker(worker1)

        self.assertEqual(results1, [worker1])
        self.assertEqual(results2, [worker2])
