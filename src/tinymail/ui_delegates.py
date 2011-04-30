import sys
import os, os.path
import logging
import email
import objc
from Foundation import NSObject, NSURL, NSString, NSISOLatin1StringEncoding
import AppKit
from PyObjCTools import Debugging
from blinker import signal
from tinymail.account import Account

_signals = [signal(name) for name in
            ('ui-folder-selected', 'ui-message-selected')]


class FolderListingItem(NSObject):
    @classmethod
    def itemWithFolder_(cls, folder):
        item = FolderListingItem.alloc().init()
        item.folder = folder
        return item


class AccountController(NSObject):
    def init(self):
        self = super(AccountController, self).init()
        self.items = []
        self.outline_view = None
        return self

    @classmethod
    def newBlank(cls):
        return cls.alloc().init()

    @classmethod
    def newWithAccount_(cls, account):
        self = cls.alloc().init()
        self.cb = lambda a: self.folders_updated(a)
        signal('account-updated').connect(self.cb, account)
        self.folders_updated(account)
        return self

    def setView_(self, outline_view):
        self.outline_view = outline_view
        if outline_view is None:
            return

        outline_view.setDataSource_(self)
        outline_view.setDelegate_(self)

        outline_view.reloadData()

    def folders_updated(self, account):
        self.items[:] = [FolderListingItem.itemWithFolder_(f)
                         for n, f in sorted(account._folders.items())]

        if self.outline_view is not None:
            self.outline_view.reloadData()

    def outlineView_numberOfChildrenOfItem_(self, outline_view, item):
        assert item is None
        return len(self.items)

    def outlineView_isItemExpandable_(self, outline_view, item):
        assert isinstance(item, FolderListingItem)
        return False

    def outlineView_child_ofItem_(self, outline_view, child, item):
        assert item is None and -1 < child < len(self.items)
        output = self.items[child]
        return output

    def outlineView_objectValueForTableColumn_byItem_(self, outline_view,
                                                      tableColumn, item):
        assert isinstance(item, FolderListingItem)
        return item.folder.name

    def outlineView_shouldEditTableColumn_item_(self, outline_view,
                                                tableColumn, item):
        return False

    def outlineViewSelectionDidChange_(self, notification):
        outline_view = notification.object()
        row = outline_view.selectedRow()
        if row == -1:
            new_value = None
        else:
            new_value = outline_view.itemAtRow_(row).folder

        signal('ui-folder-selected').send(self, folder=new_value)


class FolderController(NSObject):
    def init(self):
        self = super(FolderController, self).init()
        self.messages = []
        self.table_view = None
        return self

    @classmethod
    def newBlank(cls):
        return cls.alloc().init()

    @classmethod
    def controllerWithFolder_(cls, folder):
        self = cls.alloc().init()
        self.cb = lambda f: self.messages_updated(f._messages)
        signal('folder-updated').connect(self.cb, folder)
        self.messages_updated(folder._messages)
        return self

    def setView_(self, table_view):
        self.table_view = table_view
        if table_view is None:
            return

        table_view.setDelegate_(self)
        table_view.setDataSource_(self)
        table_view.reloadData()

    def messages_updated(self, messages):
        self.messages = [msg for (uid, msg) in sorted(messages.iteritems())]
        if self.table_view is not None:
            self.table_view.reloadData()

    def numberOfRowsInTableView_(self, table_view):
        return len(self.messages)

    def tableView_objectValueForTableColumn_row_(self, table_view, col, row):
        msg = self.messages[row]
        name = col.identifier()
        headers = email.message_from_string(msg.raw_headers)

        if name == 'Subject':
            return headers['Subject']

        elif name == 'From':
            return headers['From']

        elif name == 'Date':
            return headers['Date']

        elif name == 'Unread':
            if '\\Seen' in msg.flags:
                return ""
            else:
                return "*"

        elif name == 'Flagged':
            if '\\Flagged' in msg.flags:
                return "*"
            else:
                return ""

    def tableView_shouldSelectTableColumn_(self, table_view, col):
        return False

    def tableView_shouldEditTableColumn_row_(self, table_view, col, row):
        return False

    def tableViewSelectionDidChange_(self, notification):
        table_view = notification.object()
        row = table_view.selectedRow()
        new_value = (None if row == -1 else self.messages[row])

        signal('ui-message-selected').send(self, message=new_value)


class MessageController(NSObject):
    def init(self):
        self = super(MessageController, self).init()
        self.message = None
        self.web_view = None
        return self

    @classmethod
    def newBlank(cls):
        return cls.alloc().init()

    @classmethod
    def controllerWithMessage_(cls, message):
        self = cls.alloc().init()
        self.message = message
        return self

    def update_view_with_string(self, str_data):
        if self.web_view is None:
            return

        ns_str = NSString.stringWithString_(str_data.decode('latin-1'))
        data = ns_str.dataUsingEncoding_(NSISOLatin1StringEncoding)
        url = NSURL.URLWithString_('about:blank')
        frame = self.web_view.mainFrame()
        frame.loadData_MIMEType_textEncodingName_baseURL_(data, 'text/plain',
                                                          'latin-1', url)

    def setView_(self, web_view):
        self.web_view = web_view
        if web_view is None:
            return

        web_view_prefs = self.web_view.preferences()
        web_view_prefs.setJavaEnabled_(False)
        web_view_prefs.setJavaScriptEnabled_(False)
        web_view_prefs.setPlugInsEnabled_(False)
        web_view_prefs.setUsesPageCache_(False)

        if self.message is None:
            self.update_view_with_string("")
            return

        def show_full_message(message):
            self.update_view_with_string(message.raw_full)

        self.update_view_with_string("Loading...")
        full_message_cb = self.message.load_full()
        full_message_cb.add(show_full_message)


class ActivityDelegate(NSObject):
    @classmethod
    def create(cls, table_view):
        self = cls.alloc().init()
        self.table_view = table_view
        table_view.setDelegate_(self)
        table_view.setDataSource_(self)
        #self.reg.subscribe('maildata.op_queued', self.handle_op_queued)
        #self.reg.subscribe('maildata.op_status', self.handle_op_status)
        #self.reg.subscribe('maildata.op_finished', self.handle_op_finished)
        return self

    def init(self):
        self.state_msgs = []
        self.in_flight_ops = []
        return super(ActivityDelegate, self).init()

    def connect(self, config):
        in_queue, quit = spin_off(get_imap_loop(config))
        self.servers['single-account'] = {'in_queue': in_queue, 'quit': quit}
        return lambda op: self.queue_op('single-account', op)

    def handle_op_status(self, op):
        i = self.in_flight_ops.index(op)
        self.state_msgs[i] = u"%s [%s]" % (op.label(), op.state_msg)
        self.table_view.reloadData()

    def handle_op_finished(self, op):
        i = self.in_flight_ops.index(op)
        del self.in_flight_ops[i]
        del self.state_msgs[i]
        self.table_view.reloadData()

    def handle_op_queued(self, op):
        self.in_flight_ops.append(op)
        self.state_msgs.append('')
        self.handle_op_status(op)

    def numberOfRowsInTableView_(self, table_view):
        return len(self.state_msgs)

    def tableView_objectValueForTableColumn_row_(self, table_view, col, row):
        return self.state_msgs[row]

    def tableView_shouldSelectTableColumn_(self, table_view, col):
        return False

    def tableView_shouldEditTableColumn_row_(self, table_view, col, row):
        return False


class tinymailAppDelegate(NSObject):
    window = objc.IBOutlet()
    foldersPane = objc.IBOutlet()
    messagesPane = objc.IBOutlet()
    messageView = objc.IBOutlet()
    activityTable = objc.IBOutlet()

    def init(self):
        self = super(tinymailAppDelegate, self).init()
        self.controllers = { # because we have ownership of the controllers
            'account': AccountController.newBlank(),
            'folder': FolderController.newBlank(),
            'message': MessageController.newBlank(),
        }
        return self

    def setAccountController_(self, ac):
        self.controllers['account'].setView_(None)
        self.controllers['account'] = ac
        self.controllers['account'].setView_(self.foldersPane)

    def setFolderController_(self, fc):
        self.controllers['folder'].setView_(None)
        self.controllers['folder'] = fc
        self.controllers['folder'].setView_(self.messagesPane)

    def setMessageController_(self, mc):
        self.controllers['message'].setView_(None)
        self.controllers['message'] = mc
        self.controllers['message'].setView_(self.messageView)

    def applicationDidFinishLaunching_(self, notification):
        if devel_action == 'nose':
            self.run_nose_tests(notification.object())
            return

        if devel_action == 'devel':
            self.set_up_debug()

        if len(sys.argv) > 1:
            config_path = sys.argv[1]
        else:
            config_path = os.path.join(os.environ['HOME'], '.tinymail')
        self.configuration = Configuration(config_path)
        from plugin import load_plugins
        load_plugins(self.configuration)
        self.the_db = open_db(self.configuration)
        self.set_up_ui()

    def applicationWillTerminate_(self, notification):
        if hasattr(self, 'the_db'):
            self.the_db.close()

    def run_nose_tests(self, app):
        import runtests
        cb = runtests.main_o()
        cb.add(lambda _ign: app.terminate_(self))

    def set_up_debug(self):
        Debugging.installPythonExceptionHandler()
        logging.basicConfig(level=logging.INFO)

    def set_up_ui(self):
        self.the_account = Account(self.configuration.settings, self.the_db)
        self.setAccountController_(AccountController.newWithAccount_(self.the_account))
        self.the_account.perform_update()

        def folder_selected(sender, folder):
            fc = FolderController.controllerWithFolder_(folder)
            self.setFolderController_(fc)
        signal('ui-folder-selected').connect(folder_selected, weak=False)

        def message_selected(sender, message):
            mc = MessageController.controllerWithMessage_(message)
            self.setMessageController_(mc)
        signal('ui-message-selected').connect(message_selected, weak=False)

    @objc.IBAction
    def doSync_(self, sender):
        self.the_account.perform_update()

class Configuration(object):
    def __init__(self, home):
        self.home = home
        cfg_path = os.path.join(self.home, 'account.json')
        import json
        with open(cfg_path, 'rb') as f:
            self.settings = json.loads(f.read())

def open_db(configuration):
    from tinymail.localdata import open_local_db
    db_path = os.path.join(configuration.home, 'db.sqlite3')
    return open_local_db(db_path)
