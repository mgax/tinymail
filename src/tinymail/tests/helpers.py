from contextlib import contextmanager
import unittest2

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

@contextmanager
def mock_worker(**folders):
    from mock import Mock, patch
    from monocle.callback import defer
    from tinymail.imap_worker import ImapWorker

    worker = Mock(spec=ImapWorker)
    state = {}

    messages_in_folder = {}
    message_headers_in_folder = {}
    folder_uidvalidity = {}
    for name in folders:
        messages = {}
        message_headers = {}
        folder_uidvalidity[name] = folders[name].pop('UIDVALIDITY', 123456)
        for i, (uid, spec) in enumerate(folders[name].iteritems()):
            if spec is None:
                spec = (uid, set(), "PLACEHOLDER HEADER")
            messages[uid] = {'index': i, 'flags': set(spec[1])}
            message_headers[i] = spec[2]
        messages_in_folder[name] = messages
        message_headers_in_folder[name] = message_headers

    worker.connect.return_value = defer(None)

    worker.get_mailbox_names.return_value = defer(list(folders))

    def get_messages_in_folder(name):
        state['name'] = name
        mbox_status = {'UIDVALIDITY': folder_uidvalidity[name]}
        return defer([mbox_status, messages_in_folder[name]])
    worker.get_messages_in_folder.side_effect = get_messages_in_folder

    def get_message_headers(indices):
        name = state['name']
        message_headers = {}
        for i in indices:
            message_headers[i] = message_headers_in_folder[name][i]
        return defer(message_headers)
    worker.get_message_headers.side_effect = get_message_headers

    worker.disconnect.return_value = defer(None)

    worker._messages = messages

    with patch('tinymail.account.get_worker', Mock(return_value=worker)):
        yield worker

class AsyncTestCase(unittest2.TestCase):
    def run(self, result=None):
        from nose import SkipTest
        raise SkipTest("This test will only run in async mode")
