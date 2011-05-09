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
def mock_worker(**imap_spec):
    from mock import Mock, patch
    from monocle.callback import defer
    from tinymail.imap_worker import ImapWorker

    worker = Mock(spec=ImapWorker)
    worker.done = Mock() # `done` is implemented by `AsyncWorkerProxy`
    state = {}

    folders = {}
    for name, mbox_spec in imap_spec.iteritems():
        folder = folders[name] = {'flags': {}, 'headers': {}, 'index': {}}
        folder['uidvalidity'] = mbox_spec.pop('UIDVALIDITY', 123456)
        for i, (uid, msg_spec) in enumerate(mbox_spec.iteritems()):
            if msg_spec is None:
                msg_spec = (uid, set(), "PLACEHOLDER HEADER")
            folder['flags'][uid] = msg_spec[1]
            folder['index'][uid] = i
            folder['headers'][i] = msg_spec[2]

    worker.connect.return_value = defer(None)

    worker.get_mailbox_names.return_value = defer(list(folders))

    def select_mailbox(name, readonly=True):
        state['name'] = name
        return defer({'MESSAGES': len(folders[name]['flags']),
                      'UIDVALIDITY': folders[name]['uidvalidity']})
    worker.select_mailbox = select_mailbox

    worker.get_message_flags = lambda: defer(folders[state['name']]['flags'])

    def get_message_headers(uid_list):
        name = state['name']
        message_headers = {}
        for uid in uid_list:
            i = folders[name]['index'][uid]
            message_headers[uid] = folders[name]['headers'][i]
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
