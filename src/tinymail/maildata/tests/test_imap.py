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
        out = list(server.get_mailboxes())
        self.assertEqual(out, ['folder one', 'folder two'])
