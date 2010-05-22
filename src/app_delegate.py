import traceback

from Foundation import NSObject

class tinymailAppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, sender):
        #imap_trial()

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
