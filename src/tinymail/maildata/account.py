from async import assert_main_thread, connect_to_server, MailDataOp
from folder import Folder


class Account(object):
    def __init__(self, reg, config):
        self.reg = reg
        self.folders = []
        self._needs_update = True
        self._configure(config)

    def _configure(self, config):
        remote = connect_to_server(self.reg, config)
        (self.remote_do, self.remote_cleanup) = remote

    def update_if_needed(self):
        if self._needs_update:
            self._needs_update = False
            self.remote_do(ListFoldersOp(account=self))

    def sync_folders(self):
        for folder in self.folders:
            folder.sync()

    @assert_main_thread
    def _received_folder_list(self, imap_folders):
        self.folders[:] = [Folder(self, imap_name)
                           for imap_name in imap_folders]
        self.reg.notify((self, 'folders_updated'), account=self)
        self.sync_folders()

    def cleanup(self):
        self.remote_cleanup()

class ListFoldersOp(MailDataOp):
    def perform(self, server):
        return server.get_mailboxes()

    def report(self, result):
        self.account._received_folder_list(result)
