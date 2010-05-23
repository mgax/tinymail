import traceback

from Foundation import NSObject, objc

from tinymail.maildata.imapconn import ImapServerConnection
from folder_listing import set_up_folder_listing

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
    return ImapServerConnection(**dict( (str(k),v) for (k,v) in cfg_data ))
