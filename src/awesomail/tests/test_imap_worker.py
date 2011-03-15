import imaplib
import unittest
from mock import Mock

class ImapWorkerTest(unittest.TestCase):
    def test_get_mailbox_names(self):
        from awesomail.imap_worker import ImapWorker
        worker = ImapWorker()
        imap_conn = worker.conn = Mock(spec=imaplib.IMAP4)
        imap_conn.list.return_value = ('OK', [
            r'(\HasNoChildren) "." INBOX',
            r'(\HasNoChildren) "." "fol1"',
            r'(\HasChildren) "." "fol2"',
            r'(\HasNoChildren) "." "fol2.sub"',
        ])

        names = worker.get_mailbox_names()

        self.assertEqual(sorted(names), ['INBOX', 'fol1', 'fol2', 'fol2.sub'])
