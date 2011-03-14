import unittest
import monocle
from mock import patch

@monocle.o
def add_one(value):
    yield monocle.Return(value + 1)

class AsynchJobTest(unittest.TestCase):
    def test_simple_job(self):
        out = {}
        from awesomail.asynch import AsynchJob
        class MyJob(AsynchJob):
            @monocle.o
            def do_stuff(self):
                out['result'] = yield add_one(12)

        MyJob().start()

        self.assertEqual(out, {'result': 13})

    def test_exception_in_job(self):
        from awesomail.asynch import AsynchJob
        class MyJob(AsynchJob):
            @monocle.o
            def do_stuff(self):
                raise ValueError('ha!')

        job = MyJob()
        job.start()
        self.assertTrue(isinstance(job.failure, ValueError))
        self.assertEqual(job.failure.message, 'ha!')

class AsynchWorkerTest(unittest.TestCase):
    def setUp(self):
        from awesomail import asynch
        self._patch = patch.object(asynch, 'call_on_main_thread')
        m = self._patch.start()
        m.side_effect = lambda callback, result: callback(result)

    def tearDown(self):
        self._patch.stop()

    def test_input_queue(self):
        called = []
        from awesomail.asynch import start_worker
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
        from awesomail.asynch import start_worker
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
        from awesomail.asynch import start_worker
        class MyWorker(object):
            def freak_out(self):
                raise ValueError('hi')

        try:
            worker = start_worker(MyWorker())
            d = worker.freak_out()
        finally:
            worker.done()

        self.assertTrue(isinstance(d.result, ValueError))
        self.assertEqual(d.result.message, 'hi')
