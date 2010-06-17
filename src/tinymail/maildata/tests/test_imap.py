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

    def status(self, mbox_name, spec):
        self.called('status %r %r' % (mbox_name, spec))
        assert spec[0] == '(' and spec[-1] == ')'
        mbox = self.mbox_data[mbox_name]

        data_items = []
        for spec_name in spec[1:-1].split(' '):
            if spec_name == 'MESSAGES':
                value = len(mbox['messages'])
            elif spec_name == 'UIDNEXT':
                value = mbox['uidnext']
            elif spec_name == 'UIDVALIDITY':
                value = mbox['uidnext']
            else:
                raise NotImplementedError

            data_items.append('%s %s' % (spec_name, value))

        return 'OK', ['"%s" (%s)' % (mbox_name, ' '.join(data_items))]

    def search(self, *args):
        self.called('search')
        return 'OK', [' '.join(map(str, sorted(self._n_to_uid)))]

    def fetch(self, message_ids, spec):
        self.called('fetch %r %r' % (message_ids, spec))
        assert spec[0] == '(' and spec[-1] == ')'
        spec_names = spec[1:-1].split(' ')

        class FetchParts(object):
            def __init__(self, uid, message):
                self.uid = uid
                self.message = message

            def __getitem__(self, spec):
                if spec == 'BODY.PEEK[HEADER]':
                    header = self.message['headers']
                    return {'preamble': 'BODY[HEADER] {%d}' % len(header),
                            'data': header}
                elif spec == 'FLAGS':
                    flags = ' '.join(self.message.get('flags', []))
                    return {'preamble': 'FLAGS (%s)' % flags, 'data': ''}
                elif spec == 'RFC822':
                    full = self.message['full']
                    return {'preamble': 'RFC822 {%d}' % len(full),
                            'data': full}
                elif spec == 'UID':
                    return {'preamble': 'UID %d' % self.uid, 'data': ''}
                else:
                    raise NotImplementedError

        if message_ids == '1:*':
            requested_numbers = sorted(self._n_to_uid)
        else:
            requested_numbers = map(int, message_ids.split(','))

        output_data = []
        for n in requested_numbers:
            uid = self._n_to_uid[n]
            fetch_parts = FetchParts(uid, self._messages[uid])
            parts = [fetch_parts[name] for name in spec_names]
            preamble = '%d (%s' % (n, ' '.join(p['preamble'] for p in parts))
            data_piece = ''.join(p['data'] for p in parts)

            if data_piece:
                output_data.append( (preamble, data_piece) )
                output_data.append(')')
            else:
                output_data.append(preamble+')')

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
        server = mock_server({'testfolder': {'uidnext': 13, 'uidvalidity': 22,
            'messages': {
                5: {'headers': ('From: somebody@example.com\r\n'
                                'To: somebody_else@example.com\r\n\r\n'),
                    'flags': [r'\Seen']},
                6: {'headers': 'Content-Type: text/plain\r\n\r\n',
                    'flags': [r'\Answered', r'\Seen']},
            },
        }}, called.append)

        with server.mailbox('testfolder') as mbox:
            out = mbox.message_headers(set([5, 6]))
        self.assertTrue("fetch '1,2' '(BODY.PEEK[HEADER] FLAGS)'" in called)
        self.assertTrue(isinstance(out, dict))
        self.assertEqual(len(out), 2)
        self.assertEqual(set(out.keys()), set([5, 6]))
        self.assertTrue('From: somebody@example.com' in out[5])
        self.assertTrue('Content-Type: text/plain' in out[6])

class GetFullMessageTest(unittest.TestCase):
    def test_simple(self):
        mime_headers = ('From: somebody@example.com\r\n'
                        'To: somebody_else@example.com\r\n\r\n')
        mime_full = mime_headers + 'Hello world\r\n'
        called = []
        server = mock_server({'testfolder': {'uidnext': 13, 'uidvalidity': 22,
            'messages': {
                3: {'headers': 'some mime header stuff'},
                5: {'headers': mime_headers,
                    'full': mime_full},
            },
        }}, called.append)

        with server.mailbox('testfolder') as mbox:
            out = mbox.full_message(5)
        self.assertEqual(out, mime_full)
        self.assertTrue("fetch '2' '(RFC822)'" in called)

class MailboxStatusTest(unittest.TestCase):
    def test_simple(self):
        called = []
        server = mock_server({'testfolder': {'uidnext': 13, 'uidvalidity': 22,
            'messages': {3: {}, 5: {}},
        }}, called.append)

        mbox = server.mailbox('testfolder')
        expected = ["select 'testfolder'",
                    "status 'testfolder' '(MESSAGES UIDNEXT UIDVALIDITY)'",
                    "fetch '1:*' '(UID FLAGS)'"]
        self.assertEqual(called, expected)

        expected_status = {'UIDNEXT': 13, 'UIDVALIDITY': 13, 'MESSAGES': 2}
        self.assertEqual(mbox.status, expected_status)
        self.assertEqual(mbox.uid_to_num, {3: 1, 5: 2})
        self.assertEqual(mbox.num_to_uid, {1: 3, 2: 5})
