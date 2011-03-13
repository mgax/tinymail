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
