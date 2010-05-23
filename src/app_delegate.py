import traceback

from Foundation import NSObject, objc

class tinymailAppDelegate(NSObject):
    window = objc.IBOutlet()
    foldersPane = objc.IBOutlet()

    def applicationDidFinishLaunching_(self, notification):
        self.imap_server = connect_to_imap_server()
        set_up_folder_listing(self.imap_server, self.foldersPane)

    def applicationWillTerminate_(self, notification):
        self.imap_server.cleanup()

def connect_to_imap_server():
    import os
    from os import path
    import json
    cfg_path = path.join(os.environ['HOME'], '.tinymail/account.json')
    with open(cfg_path, 'rb') as f:
        cfg_data = json.loads(f.read()).items()

    from tinymail.maildata.imapconn import ImapServerConnection
    return ImapServerConnection(**dict( (str(k),v) for (k,v) in cfg_data ))

def set_up_folder_listing(imap_conn, folders_tree):
    from tinymail.ui.folder_listing import FolderListingDataSource
    folder_paths = list(imap_conn.get_mailboxes())
    ds = FolderListingDataSource.sourceWithFolderPaths_(folder_paths)
    folders_tree.setDataSource_(ds)
    folders_tree.setDelegate_(ds)
