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
    worker.done = Mock() # `done` is implemented by `AsyncWorkerProxy`
    state = {}

    message_index_of_folder = {}
    flags_in_folder = {}
    message_headers_in_folder = {}
    folder_uidvalidity = {}
    for name in folders:
        flags = {}
        message_headers = {}
        message_index = {}
        folder_uidvalidity[name] = folders[name].pop('UIDVALIDITY', 123456)
        for i, (uid, spec) in enumerate(folders[name].iteritems()):
            if spec is None:
                spec = (uid, set(), "PLACEHOLDER HEADER")
            flags[uid] = spec[1]
            message_index[uid] = i
            message_headers[i] = spec[2]
        flags_in_folder[name] = flags
        message_index_of_folder[name] = message_index
        message_headers_in_folder[name] = message_headers

    worker.connect.return_value = defer(None)

    worker.get_mailbox_names.return_value = defer(list(folders))

    def select_mailbox(name, readonly=True):
        state['name'] = name
        return defer({'MESSAGES': len(flags_in_folder[name]),
                      'UIDVALIDITY': folder_uidvalidity[name]})
    worker.select_mailbox = select_mailbox

    worker.get_message_flags = lambda: defer(flags_in_folder[state['name']])

    def get_message_headers(uid_list):
        name = state['name']
        message_headers = {}
        for uid in uid_list:
            i = message_index_of_folder[name][uid]
            message_headers[uid] = message_headers_in_folder[name][i]
        return defer(message_headers)
    worker.get_message_headers.side_effect = get_message_headers

    worker.change_flag.return_value = defer(None)
    worker.close_mailbox.return_value = defer(None)
    worker.disconnect.return_value = defer(None)

    with patch('tinymail.account._new_imap_worker', Mock(return_value=worker)):
        yield worker

class AsyncTestCase(unittest2.TestCase):
    def run(self, result=None):
        from nose import SkipTest
        raise SkipTest("This test will only run in async mode")
