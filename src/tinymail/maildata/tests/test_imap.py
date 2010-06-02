import unittest

from tinymail.maildata import imapserver

class TestServer(imapserver.ImapServer):
    def __init__(self, test_connection):
        self.conn = test_connection

class GetMailboxesTest(unittest.TestCase):
    def test_simple(self):
        class StubImapConnection(object):
            def list(self):
                return 'OK', [r'(\HasNoChildren) "." "folder one"',
                              r'(\HasNoChildren) "." "folder two"']

        server = TestServer(StubImapConnection())
        out = server.get_mailboxes()
        self.assertEqual(out, ['folder one', 'folder two'])

    def test_error_response(self):
        class StubImapConnection(object):
            def list(self):
                return "anything that's not 'OK'", ""

        server = TestServer(StubImapConnection())
        self.assertRaises(AssertionError, server.get_mailboxes)

    def test_malformed_response(self):
        class StubImapConnection(object):
            def list(self):
                return "OK", ['blah blah']

        server = TestServer(StubImapConnection())
        self.assertRaises(AssertionError, server.get_mailboxes)

class GetMessagesInMailbox(unittest.TestCase):
    def test_simple(self):
        called = []
        class StubImapConnection(object):
            def select(self, mailbox, readonly):
                assert readonly is True
                assert mailbox == 'testfolder'
                called.append('select')
                return 'OK', []

            def search(self, *args):
                called.append('search')
                return 'OK', ['1 2']

            def fetch(self, msg_ids, spec):
                assert msg_ids == '1,2'
                called.append('fetch')
                return 'OK', [
                    ('1 (FLAGS (\\Seen) BODY[HEADER] {60}',
                      'From: somebody@example.com\r\n'
                      'To: somebody_else@example.com\r\n\r\n'),
                    ')',
                    ('2 (FLAGS (\\Answered \\Seen) BODY[HEADER] {28}',
                      'Content-Type: text/plain\r\n\r\n'),
                    ')',
                ]

        server = TestServer(StubImapConnection())
        out = list(server.get_messages_in_mailbox('testfolder'))
        self.assertEqual(len(out), 2)
        self.assertEqual([o[0] for o in out], ['1', '2'])
        self.assertTrue('From: somebody@example.com' in out[0][1])
        self.assertTrue('Content-Type: text/plain' in out[1][1])

        self.assertEqual(called, ['select', 'search', 'fetch'])

    def test_empty_folder(self):
        called = []
        class StubImapConnection(object):
            def select(self, mailbox, readonly):
                called.append('select')
                return 'OK', []

            def search(self, *args):
                called.append('search')
                return 'OK', ['']

        server = TestServer(StubImapConnection())
        out = list(server.get_messages_in_mailbox('testfolder'))
        self.assertEqual(out, [])
        self.assertEqual(called, ['select', 'search'])

class GetFullMessageTest(unittest.TestCase):
    def test_simple(self):
        msg = ('From: somebody@example.com\r\n'
               'To: somebody_else@example.com\r\n\r\n'
               'Hello world\r\n')
        called = []
        class StubImapConnection(object):
            def select(self, mailbox, readonly):
                assert readonly is True
                assert mailbox == 'testfolder'
                called.append('select')
                return 'OK', []

            def fetch(self, message_id, spec):
                called.append('fetch')
                assert message_id == '2'
                assert spec == '(RFC822)'
                return 'OK', [('3 (RFC822 {%d}' % len(msg), msg), ')']

        server = TestServer(StubImapConnection())
        out = server.get_full_message('testfolder', '2')
        self.assertEqual(out, msg)
        self.assertEqual(called, ['select', 'fetch'])
