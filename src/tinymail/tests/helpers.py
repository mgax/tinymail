from contextlib import contextmanager

def mock_db():
    from tinymail.localdata import open_local_db
    return open_local_db(':memory:')

@contextmanager
def listen_for(signal):
    caught_signals = []

    def handler(sender, **kwargs):
        caught_signals.append( (sender, kwargs) )

    with signal.connected_to(handler):
        yield caught_signals
