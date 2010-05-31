from imapconn import get_imap_loop
from async import spin_off, assert_main_thread, MailDataOp
from folder import Folder


class Account(object):
    def __init__(self, reg, config):
        self.reg = reg
        self.remote_do, self.remote_cleanup = spin_off(get_imap_loop(config))
        self.folders = []
        self._needs_update = True

    def update_if_needed(self):
        if self._needs_update:
            self._needs_update = False
            self.remote_do(ListFoldersOp(account=self))

    @assert_main_thread
    def _imap_folder_list_loaded(self, imap_folders):
        self.folders[:] = [Folder(self, imap_name)
                           for imap_name in imap_folders]
        self.reg.notify((self, 'folders_updated'), account=self)

    def cleanup(self):
        self.remote_cleanup()

class ListFoldersOp(MailDataOp):
    def perform(self, imap):
        return imap.get_mailboxes()

    def report(self, result):
        self.account._imap_folder_list_loaded(result)
