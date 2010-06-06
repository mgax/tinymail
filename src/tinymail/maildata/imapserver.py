import imaplib
import re

list_pattern = re.compile(r'^\((?P<flags>[^\)]*)\) '
                          r'"(?P<delim>[^"]*)" '
                          r'(?P<name>.*)$')

class ImapServer(object):
    def __init__(self, config):
        self.config = config

    def __enter__(self):
        self.conn = imaplib.IMAP4_SSL(self.config['host'])
        self.conn.login(self.config['login_name'], self.config['login_pass'])
        return self

    def __exit__(self, *args):
        self.conn.shutdown()

    def get_mailboxes(self):
        status, entries = self.conn.list()
        assert status == 'OK'

        paths = []
        for entry in entries:
            m = list_pattern.match(entry)
            assert m is not None
            folder_path = m.group('name').strip('"')
            paths.append(folder_path)

        return paths

    def get_messages_in_mailbox(self, mbox_name):
        status, count = self.conn.select(mbox_name, readonly=True)
        assert status == 'OK'

        status, data = self.conn.search(None, 'All')
        assert status == 'OK'
        message_ids = data[0].split()

        if not message_ids:
            return

        # we need to get FLAGS too, otherwise messages are marked as read
        status, data = self.conn.fetch(','.join(message_ids),
                                       '(BODY.PEEK[HEADER] FLAGS)')
        assert status == 'OK'
        data = iter(data)
        while True:
            fragment = next(data)
            assert len(fragment) == 2, 'unexpected fragment layout'
            preamble, headers = fragment
            assert 'BODY[HEADER]' in preamble, 'bad preamble'

            message_id = preamble.split(' ', 1)[0]
            mime_headers = headers

            yield int(message_id), mime_headers

            closing = next(data, None)
            assert closing == ')', 'bad closing'

    def get_full_message(self, mbox_name, message_id):
        status, count = self.conn.select(mbox_name, readonly=True)
        assert status == 'OK'

        status, data = self.conn.fetch(str(message_id), '(RFC822)')
        assert status == 'OK'
        assert len(data) == 2 and data[1] == ')'
        assert isinstance(data[0], tuple) and len(data[0]) == 2

        return data[0][1]

def get_imap_loop(config):
    def run_loop(in_queue):
        with ImapServer(config) as server:
            while True:
                cmd = in_queue.get()
                if cmd is None:
                    break
                else:
                    cmd(server)

    return run_loop
