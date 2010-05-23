import traceback

from Foundation import NSObject, objc

class tinymailAppDelegate(NSObject):
    window = objc.IBOutlet()
    foldersPane = objc.IBOutlet()

    def applicationDidFinishLaunching_(self, sender):
        #imap_trial()

        # set up folder listing
        from tinymail.ui.folder_listing import FolderListingDataSource
        folder_paths = ['asdf', 'qewr']
        s = FolderListingDataSource.sourceWithFolderPaths_(folder_paths)
        self.foldersPane.setDataSource_(s)
        self.foldersPane.setDelegate_(s)

def imap_trial():
    import os
    from os import path
    import json
    cfg_path = path.join(os.environ['HOME'], '.tinymail/account.json')
    with open(cfg_path, 'rb') as f:
        cfg_data = json.loads(f.read()).items()

    from tinymail.maildata.imapconn import ImapServerConnection
    sc = ImapServerConnection(**dict( (str(k),v) for (k,v) in cfg_data ))
    for name in sc.get_mailboxes():
        print name
    sc.cleanup()
