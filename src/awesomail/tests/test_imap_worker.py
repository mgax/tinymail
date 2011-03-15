import imaplib
import unittest
from mock import Mock, patch

class ImapWorkerTest(unittest.TestCase):
    def _worker_with_fake_imap(self):
        from awesomail.imap_worker import ImapWorker
        worker = ImapWorker()
        imap_conn = worker.conn = Mock(spec=imaplib.IMAP4)
        return worker, imap_conn

    @patch('awesomail.imap_worker.imaplib')
    def test_connect(self, mock_imaplib):
        mock_conn = Mock(spec=imaplib.IMAP4)
        mock_imaplib.IMAP4_SSL.return_value = mock_conn

        from awesomail.imap_worker import ImapWorker
        worker = ImapWorker()
        worker.connect('test_host', 'test_login', 'test_pass')

        self.assertTrue(worker.conn is mock_conn)
        mock_imaplib.IMAP4_SSL.assert_called_once_with('test_host')
        mock_conn.login.assert_called_once_with('test_login', 'test_pass')

    def test_get_mailbox_names(self):
        worker, imap_conn = self._worker_with_fake_imap()
        imap_conn.list.return_value = ('OK', [
            r'(\HasNoChildren) "." INBOX',
            r'(\HasNoChildren) "." "fol1"',
            r'(\HasChildren) "." "fol2"',
            r'(\HasNoChildren) "." "fol2.sub"',
        ])

        names = worker.get_mailbox_names()

        self.assertEqual(sorted(names), ['INBOX', 'fol1', 'fol2', 'fol2.sub'])

    def test_get_messages_in_folder(self):
        worker, imap_conn = self._worker_with_fake_imap()
        imap_conn.select.return_value = ('OK', [])
        imap_conn.status.return_value = ('OK', [
            '"fol1" (MESSAGES 3 RECENT 1 UIDNEXT 14 '
                    'UIDVALIDITY 1300189203 UNSEEN 1)'])
        imap_conn.fetch.return_value = ('OK', [
            '1 (UID 6 FLAGS (\\Seen))',
            '2 (UID 8 FLAGS (\\Answered \\Seen))',
            '3 (UID 13 FLAGS ())',
        ])

        mbox_status, message_data = worker.get_messages_in_folder('fol1')

        imap_conn.select.assert_called_once_with('fol1', readonly=True)
        imap_conn.status.assert_called_once_with(
            'fol1', '(MESSAGES UIDNEXT UIDVALIDITY)')
        imap_conn.fetch.assert_called_once_with('1:*', '(UID FLAGS)')

        self.assertEqual(mbox_status, {
            'UIDNEXT': 14,
            'UIDVALIDITY': 1300189203,
            'MESSAGES': 3,
            'UNSEEN': 1,
            'RECENT': 1,
        })
        self.assertEqual(message_data, {
            6: {'index': 1, 'flags': set([r'\Seen'])},
            8: {'index': 2, 'flags': set([r'\Answered', r'\Seen'])},
            13: {'index': 3, 'flags': set()},
        })

    def test_get_message_headers(self):
        worker, imap_conn = self._worker_with_fake_imap()
        hdr = ('From: somebody@example.com\r\n'
               'To: somebody_else@example.com\r\n'
               'Subject: One test message!\r\n'
               '\r\n')
        imap_conn.fetch.return_value = ('OK', [
            ('1 (BODY[HEADER] {%s} FLAGS (\\Seen)' % len(hdr), hdr), ')',
            ('2 (BODY[HEADER] {%s} FLAGS (\\Seen)' % len(hdr), hdr), ')',
            ('5 (BODY[HEADER] {%s} FLAGS (\\Seen)' % len(hdr), hdr), ')',
        ])

        header_by_index = worker.get_message_headers([1, 2, 5])

        imap_conn.fetch.assert_called_once_with('1,2,5',
                                                '(BODY.PEEK[HEADER] FLAGS)')
        self.assertEqual(header_by_index, {1: hdr, 2: hdr, 5: hdr})
