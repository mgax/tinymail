import unittest

from tinymail.maildata import imapserver

class MockImapConnection(object):
    def __init__(self, mbox_data, called):
        self.mbox_data = mbox_data
        self.called = called

    def list(self):
        self.called('list')
        data = [r'(\HasNoChildren) "." "%s"' % name for name in self.mbox_data]
        return 'OK', data

    def select(self, mbox_name, readonly):
        assert readonly is True
        assert mbox_name in self.mbox_data
        self.called('select %r' % mbox_name)
        self._selected_mbox = mbox_name
        self._messages = self.mbox_data[self._selected_mbox]['messages']
        self._n_to_uid = dict( (n+1, uid) for (n, uid) in
                               enumerate(sorted(self._messages)) )
        return 'OK', []

    def search(self, *args):
        self.called('search')
        return 'OK', [' '.join(map(str, sorted(self._n_to_uid)))]

    def fetch(self, message_ids, spec):
        self.called('fetch %r %r' % (message_ids, spec))
        assert spec[0] == '(' and spec[-1] == ')'
        spec_names = spec[1:-1].split(' ')

        class FetchParts(object):
            def __init__(self, message):
                self.message = message

            def __getitem__(self, spec):
                if spec == 'BODY.PEEK[HEADER]':
                    header = self.message['headers']
                    return {'preamble': 'BODY[HEADER] {%d}' % len(header),
                            'data': header}
                elif spec == 'FLAGS':
                    flags = ' '.join(self.message['flags'])
                    return {'preamble': 'FLAGS (%s)' % flags, 'data': ''}

                elif spec == 'RFC822':
                    full = self.message['full']
                    return {'preamble': 'RFC822 {%d}' % len(full),
                            'data': full}

                else:
                    raise NotImplementedError

        output_data = []
        for n in map(int, message_ids.split(',')):
            fetch_parts = FetchParts(self._messages[self._n_to_uid[n]])
            parts = [fetch_parts[name] for name in spec_names]
            preamble = '%d (%s' % (n, ' '.join(p['preamble'] for p in parts))
            data_piece = ''.join(p['data'] for p in parts)

            output_data.append( (preamble, data_piece) )
            output_data.append(')')

        return 'OK', output_data

class MockServer(imapserver.ImapServer):
    def __init__(self, test_connection):
        super(MockServer, self).__init__(None)
        self.conn = test_connection

def mock_server(mbox_data, called=lambda x: None):
    return MockServer(MockImapConnection(mbox_data, called))

class GetMailboxesTest(unittest.TestCase):
    def test_simple(self):
        server = mock_server({'folder one':{}, 'folder two':{}})
        out = server.get_mailboxes()
        self.assertEqual(set(out), set(['folder one', 'folder two']))

class GetMessagesInMailbox(unittest.TestCase):
    def test_simple(self):
        called = []
        server = mock_server({'testfolder': {
            'messages': {
                5: {'headers': ('From: somebody@example.com\r\n'
                                'To: somebody_else@example.com\r\n\r\n'),
                    'flags': [r'\Seen']},
                6: {'headers': 'Content-Type: text/plain\r\n\r\n',
                    'flags': [r'\Answered', r'\Seen']},
            },
        }}, called.append)

        with server.mailbox('testfolder') as mbox:
            out = mbox.message_headers()
        self.assertTrue(isinstance(out, dict))
        self.assertEqual(len(out), 2)
        self.assertEqual(set(out.keys()), set([1, 2]))
        self.assertTrue('From: somebody@example.com' in out[1])
        self.assertTrue('Content-Type: text/plain' in out[2])

        self.assertEqual(called, ["select 'testfolder'",
                                  "search",
                                  "fetch '1,2' '(BODY.PEEK[HEADER] FLAGS)'"])

    def test_empty_folder(self):
        called = []
        server = mock_server({'testfolder': {
            'messages': {},
        }}, called.append)

        with server.mailbox('testfolder') as mbox:
            out = mbox.message_headers()
        self.assertEqual(out, {})
        self.assertEqual(called, ["select 'testfolder'", "search"])

class GetFullMessageTest(unittest.TestCase):
    def test_simple(self):
        mime_headers = ('From: somebody@example.com\r\n'
                        'To: somebody_else@example.com\r\n\r\n')
        mime_full = mime_headers + 'Hello world\r\n'
        called = []
        server = mock_server({'testfolder': {
            'messages': {
                3: {'headers': 'some mime header stuff'},
                5: {'headers': mime_headers,
                    'full': mime_full},
            },
        }}, called.append)

        with server.mailbox('testfolder') as mbox:
            out = mbox.full_message(2)
        self.assertEqual(out, mime_full)
        self.assertEqual(called, ["select 'testfolder'",
                                  "fetch '2' '(RFC822)'"])
