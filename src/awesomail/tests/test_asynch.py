import unittest
import monocle

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
