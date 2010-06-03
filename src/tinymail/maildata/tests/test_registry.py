import unittest

from tinymail.maildata.events import Registry

class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.reg = Registry()
        self.events = []

    def subscribe(self, selector, name):
        callback = lambda **kwargs: self.events.append( (name, kwargs) )
        self.reg.subscribe(selector, callback)
        return callback

    def unsubscribe(self, selector, callback):
        self.reg.unsubscribe(selector, callback)

    def assertEvents(self, *reference):
        self.assertEqual(len(reference), len(self.events))
        for item in reference:
            self.assertTrue(item in self.events)
        self.events[:] = []

    def test_basic(self):
        self.subscribe('sel1', 'first subscriber')
        self.reg.notify('sel1', msg="hello")
        self.assertEvents(('first subscriber', {'msg': 'hello'}))

    def test_two_subscribers(self):
        self.subscribe('sel1', 'first')
        self.subscribe('sel1', 'second')
        self.reg.notify('sel1', a="b")
        self.assertEvents(('first', {'a': 'b'}), ('second', {'a': 'b'}))

    def test_two_events(self):
        self.subscribe('sel', 'sub')
        self.reg.notify('sel', a="b")
        self.reg.notify('sel', c="d")
        self.assertEvents(('sub', {'a': 'b'}), ('sub', {'c': 'd'}))

    def test_discriminate(self):
        self.subscribe('sel1', 'first')
        self.subscribe('sel2', 'second')
        self.reg.notify('sel1')
        self.assertEvents(('first', {}))

    def test_unsubscribe(self):
        c1 = self.subscribe('sel', 'first')
        c2 = self.subscribe('sel', 'second')
        self.reg.notify('sel')
        self.assertEvents(('first', {}), ('second', {}))

        self.unsubscribe('sel', c1)
        self.reg.notify('sel')
        self.assertEvents(('second', {}))

        self.unsubscribe('sel', c2)
        self.reg.notify('sel')
        self.assertEvents()
