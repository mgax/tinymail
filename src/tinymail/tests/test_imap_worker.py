import imaplib
import unittest2 as unittest
from mock import Mock, patch

def worker_with_fake_imap():
    from tinymail.imap_worker import ImapWorker, ConnectionErrorWrapper
    worker = ImapWorker()
    imap_conn = Mock(spec=imaplib.IMAP4)
    worker.conn = ConnectionErrorWrapper(imap_conn)
    return worker, imap_conn

class ImapWorkerTest(unittest.TestCase):
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
        worker, imap_conn = worker_with_fake_imap()
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
        worker, imap_conn = worker_with_fake_imap()
        imap_conn.list.return_value = ('OK', ['(\\HasNoChildren) "." "f\xb3"'])

        msg = "Non-ascii mailbox names not supported"
        self.assertRaisesRegexp(ImapWorkerError, msg, worker.get_mailbox_names)

    def test_open_mailbox(self):
        worker, imap_conn = worker_with_fake_imap()
        imap_conn.select.return_value = ('OK', [])
        imap_conn.status.return_value = ('OK', [
            '"fol1" (MESSAGES 0 RECENT 1 UIDNEXT 14 '
                    'UIDVALIDITY 1300189203 UNSEEN 1)'])
        imap_conn.fetch.return_value = ('OK', [])

        mailbox_status = worker.select_mailbox('fol1')

        imap_conn.select.assert_called_once_with('fol1', readonly=True)
        imap_conn.status.assert_called_once_with(
            'fol1', '(MESSAGES UIDNEXT UIDVALIDITY)')
        self.assertEqual(mailbox_status, {
            'UIDNEXT': 14,
            'UIDVALIDITY': 1300189203,
            'MESSAGES': 0,
            'UNSEEN': 1,
            'RECENT': 1,
        })

    def test_map_uids(self):
        worker, imap_conn = worker_with_fake_imap()
        _status_data = ['"fol1" (MESSAGES 3 RECENT 1 UIDNEXT 14 '
                        'UIDVALIDITY 1300189203 UNSEEN 1)']
        _fetch_data = ['1 (UID 6)', '2 (UID 8)', '3 (UID 13)']
        imap_conn.select.return_value = ('OK', [])
        imap_conn.status.return_value = ('OK', _status_data)
        imap_conn.fetch.return_value = ('OK', _fetch_data)

        worker.select_mailbox('fol1')

        self.assertEqual(worker.message_index, {6:1, 8:2, 13:3})
        imap_conn.fetch.assert_called_once_with('1:*', '(UID)')

    def test_open_mailbox_for_writing(self):
        worker, imap_conn = worker_with_fake_imap()
        imap_conn.select.return_value = ('OK', [])
        imap_conn.status.return_value = ('OK', [
            '"fol1" (MESSAGES 0 RECENT 1 UIDNEXT 14 '
                    'UIDVALIDITY 1300189203 UNSEEN 1)'])

        mailbox_status = worker.select_mailbox('fol1', readonly=False)

        imap_conn.select.assert_called_once_with('fol1', readonly=False)

    def test_get_message_flags(self):
        worker, imap_conn = worker_with_fake_imap()
        worker.message_uid = {1:6, 2:8, 3:13}
        _flags = {6: [r'\Seen'], 8: [r'\Answered', r'\Seen'], 13: []}
        imap_conn.fetch.return_value = ('OK', [
            '1 (FLAGS (\\Seen))',
            '2 (FLAGS (\\Answered \\Seen))',
            '3 (FLAGS ())',
        ])

        message_flags = worker.get_message_flags()

        imap_conn.fetch.assert_called_once_with('1:*', '(FLAGS)')
        self.assertEqual(message_flags, _flags)

    def test_get_message_headers(self):
        worker, imap_conn = worker_with_fake_imap()
        worker.message_index = {31: 1, 32: 2, 35: 5}
        hdr = ('From: somebody@example.com\r\n'
               'To: somebody_else@example.com\r\n'
               'Subject: One test message!\r\n'
               '\r\n')
        imap_conn.fetch.return_value = ('OK', [
            ('1 (BODY[HEADER] {%s} FLAGS (\\Seen)' % len(hdr), hdr), ')',
            ('2 (BODY[HEADER] {%s} FLAGS (\\Seen)' % len(hdr), hdr), ')',
            ('5 (BODY[HEADER] {%s} FLAGS (\\Seen)' % len(hdr), hdr), ')',
        ])

        header_by_index = worker.get_message_headers([31, 32, 35])

        imap_conn.fetch.assert_called_once_with('1,2,5',
                                                '(FLAGS BODY.PEEK[HEADER])')
        self.assertEqual(header_by_index, {31: hdr, 32: hdr, 35: hdr})

    def test_get_message_body(self):
        worker, imap_conn = worker_with_fake_imap()
        worker.message_index = {22: 5}
        response_data = [('5 (RFC822 {7}', 'ZE BODY'), ')']
        imap_conn.fetch.return_value = ('OK', response_data)

        message_body = worker.get_message_body(22)

        imap_conn.fetch.assert_called_once_with('5', '(RFC822)')
        self.assertEqual(message_body, 'ZE BODY')

    def test_add_flag(self):
        worker, imap_conn = worker_with_fake_imap()
        worker.message_index = {31: 1, 32: 2, 35: 5}
        imap_conn.store.return_value = ('OK', [])

        worker.change_flag([31, 32, 35], 'add', '\\Seen')

        imap_conn.store.assert_called_once_with('1,2,5', '+FLAGS', '\\Seen')

    def test_remove_flag(self):
        worker, imap_conn = worker_with_fake_imap()
        worker.message_index = {31: 1, 32: 2, 35: 5}
        imap_conn.store.return_value = ('OK', [])

        worker.change_flag([31, 32, 35], 'del', '\\Flagged')

        imap_conn.store.assert_called_once_with('1,2,5', '-FLAGS', '\\Flagged')

    def test_close(self):
        worker, imap_conn = worker_with_fake_imap()
        imap_conn.close.return_value = ('OK', [])

        worker.close_mailbox()

        imap_conn.close.assert_called_once_with()
