import objc

def _remove_from_list(callback, the_list):
    if isinstance(callback, objc.selector):
        for i, c in enumerate(the_list):
            if c.self is callback.self and c.callable is callback.callable:
                del the_list[i]
                return
        # If we don't find it call list.remove which will raise ValueError

    the_list.remove(callback)

class Registry(object):
    def __init__(self):
        self.mapping = {}

    def subscribe(self, selector, callback):
        self.mapping.setdefault(selector, []).append(callback)

    def unsubscribe(self, selector, callback):
        the_list = self.mapping[selector]
        _remove_from_list(callback, the_list)
        if not the_list:
            del self.mapping[selector]

    def notify(self, selector, **kwargs):
        for callback in self.mapping.get(selector, ()):
            callback(**kwargs)

