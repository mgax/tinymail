import imaplib
import unittest2 as unittest
from mock import Mock, patch

class ImapWorkerTest(unittest.TestCase):
    def _worker_with_fake_imap(self):
        from tinymail.imap_worker import ImapWorker, ConnectionErrorWrapper
        worker = ImapWorker()
        imap_conn = Mock(spec=imaplib.IMAP4)
        worker.conn = ConnectionErrorWrapper(imap_conn)
        return worker, imap_conn

    @patch('tinymail.imap_worker.imaplib')
    def test_connect(self, mock_imaplib):
        mock_conn = Mock(spec=imaplib.IMAP4)
        mock_imaplib.IMAP4_SSL.return_value = mock_conn
        mock_conn.login.return_value = ('OK', [])

        from tinymail.imap_worker import ImapWorker
        worker = ImapWorker()
        worker.connect('test_host', 'test_login', 'test_pass')

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

    def test_crash_on_non_ascii_folder(self):
        from tinymail.imap_worker import ImapWorkerError
        worker, imap_conn = self._worker_with_fake_imap()
        imap_conn.list.return_value = ('OK', ['(\\HasNoChildren) "." "f\xb3"'])

        msg = "Non-ascii mailbox names not supported"
        self.assertRaisesRegexp(ImapWorkerError, msg, worker.get_mailbox_names)

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

    def test_open_mailbox_for_writing(self):
        worker, imap_conn = self._worker_with_fake_imap()
        imap_conn.select.return_value = ('OK', [])
        imap_conn.status.return_value = ('OK', [
            '"fol1" (MESSAGES 1 RECENT 1 UIDNEXT 14 '
                    'UIDVALIDITY 1300189203 UNSEEN 0)'])
        imap_conn.fetch.return_value = ('OK', ['1 (UID 6 FLAGS (\\Seen))'])

        worker.get_messages_in_folder('fol1', readonly=False)

        imap_conn.select.assert_called_once_with('fol1', readonly=False)

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
                                                '(FLAGS BODY.PEEK[HEADER])')
        self.assertEqual(header_by_index, {1: hdr, 2: hdr, 5: hdr})

    def test_get_message_body(self):
        worker, imap_conn = self._worker_with_fake_imap()
        response_data = [('5 (RFC822 {7}', 'ZE BODY'), ')']
        imap_conn.fetch.return_value = ('OK', response_data)

        message_body = worker.get_message_body(5)

        imap_conn.fetch.assert_called_once_with('5', '(RFC822)')
        self.assertEqual(message_body, 'ZE BODY')
