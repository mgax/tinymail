import imaplib
import re

list_pattern = re.compile(r'^\((?P<flags>[^\)]*)\) '
                          r'"(?P<delim>[^"]*)" '
                          r'(?P<name>.*)$')

def iter_fragments(data):
    data = iter(data)
    while True:
        yield next(data)
        assert next(data, None) == ')', 'bad closing'

class ImapMailbox(object):
    def __init__(self, server, imap_name):
        self.server = server
        self.conn = server.conn
        self.imap_name = imap_name
        self._active = False

    def __enter__(self):
        assert not self._active
        self._active = True
        return self

    def __exit__(self, *args):
        assert self._active
        self._active = False

    def message_headers(self):
        status, count = self.conn.select(self.imap_name, readonly=True)
        assert status == 'OK'

        status, data = self.conn.search(None, 'All')
        assert status == 'OK'
        message_ids = data[0].split()

        if not message_ids:
            return {}

        # we need to get FLAGS too, otherwise messages are marked as read
        status, data = self.conn.fetch(','.join(message_ids),
                                       '(BODY.PEEK[HEADER] FLAGS)')
        assert status == 'OK'

        out = {}
        for fragment in iter_fragments(data):
            assert len(fragment) == 2, 'unexpected fragment layout'
            preamble, headers = fragment
            assert 'BODY[HEADER]' in preamble, 'bad preamble'

            message_id = preamble.split(' ', 1)[0]
            mime_headers = headers

            out[int(message_id)] = mime_headers

        return out

    def full_message(self, message_id):
        status, count = self.conn.select(self.imap_name, readonly=True)
        assert status == 'OK'

        status, data = self.conn.fetch(str(message_id), '(RFC822)')
        assert status == 'OK'
        assert len(data) == 2 and data[1] == ')'
        assert isinstance(data[0], tuple) and len(data[0]) == 2

        return data[0][1]

class ImapServer(object):
    def __init__(self, config):
        self.config = config
        self._current_mailbox = None

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

    def mailbox(self, imap_name):
        """ get a context manager for working in a mailbox """

        if self._current_mailbox is not None:
            assert self._current_mailbox._active is False

            if self._current_mailbox.imap_name == imap_name:
                return self._current_mailbox

        self._current_mailbox = ImapMailbox(self, imap_name)
        return self._current_mailbox

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
