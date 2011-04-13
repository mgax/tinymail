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
        item = FolderListingItem.new()
        item.folder = folder
        return item


class FolderListing(NSObject):
    @classmethod
    def create(cls, outline_view, account):
        self = cls.new()
        self.outline_view = outline_view
        outline_view.setDataSource_(self)
        outline_view.setDelegate_(self)
        self.cb = lambda a: self.handle_folders_updated(a)
        signal('account-updated').connect(self.cb)
        self.handle_folders_updated(account)
        return self

    def init(self):
        self.items = []
        return super(FolderListing, self).init()

    def handle_folders_updated(self, account):
        for item in self.items:
            item.release()
        self.items = [FolderListingItem.itemWithFolder_(f).retain()
                      for n, f in sorted(account._folders.items())]
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


class MessageListing(NSObject):
    @classmethod
    def create(cls, table_view, folder):
        self = cls.new()
        self.table_view = table_view
        table_view.setDelegate_(self)
        table_view.setDataSource_(self)
        self._set_up_columns()
        if folder is not None:
            self.cb = lambda f: self.messages_updated(f._messages)
            signal('folder-updated').connect(self.cb, folder)
            self.messages_updated(folder._messages)
        return self

    def _set_up_columns(self):
        col0, col1 = self.table_view.tableColumns()
        col0.setIdentifier_('From')
        col0.headerCell().setTitle_("Sender")
        col1.setIdentifier_('Subject')
        col1.headerCell().setTitle_("Title")

    def init(self):
        self.messages = []
        self._folder = None
        return super(MessageListing, self).init()

    def messages_updated(self, messages):
        self.messages = [msg for (uid, msg) in sorted(messages.iteritems())]
        self.table_view.reloadData()

    def numberOfRowsInTableView_(self, table_view):
        return len(self.messages)

    def tableView_objectValueForTableColumn_row_(self, table_view, col, row):
        msg = self.messages[row]
        name = col.identifier()
        headers = email.message_from_string(msg.raw_headers)
        if name == 'Subject':
            subject = headers['Subject']
            if '\\Seen' in msg.flags:
                return subject
            else:
                return '* ' + subject
        elif name == 'From':
            return headers['From']

    def tableView_shouldSelectTableColumn_(self, table_view, col):
        return False

    def tableView_shouldEditTableColumn_row_(self, table_view, col, row):
        return False

    def tableViewSelectionDidChange_(self, notification):
        table_view = notification.object()
        row = table_view.selectedRow()
        new_value = (None if row == -1 else self.messages[row])

        signal('ui-message-selected').send(self, message=new_value)


class MessageView(NSObject):
    @classmethod
    def create(cls, web_view, message):
        self = cls.new()
        self.web_view = web_view
        if message is None:
            self._update_view_with_string("")
        else:
            self._update_view_with_string("Loading...")
            full_message_cb = message.load_full()
            full_message_cb.add(self.show_full_message)
        return self

    def _configure_web_view(self):
        web_view_prefs = self.web_view.preferences()
        web_view_prefs.setJavaEnabled_(False)
        web_view_prefs.setJavaScriptEnabled_(False)
        web_view_prefs.setPluginsEnabled_(False)
        web_view_prefs.setUsesPageCache_(False)

    def show_full_message(self, message):
        self._update_view_with_string(message.raw_full)

    def _update_view_with_string(self, str_data):
        ns_str = NSString.stringWithString_(str_data.decode('latin-1'))
        data = ns_str.dataUsingEncoding_(NSISOLatin1StringEncoding)
        url = NSURL.URLWithString_('about:blank')
        frame = self.web_view.mainFrame()
        frame.loadData_MIMEType_textEncodingName_baseURL_(data, 'text/plain',
                                                          'latin-1', url)


class ActivityDelegate(NSObject):
    @classmethod
    def create(cls, table_view):
        self = cls.new()
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

    def applicationDidFinishLaunching_(self, notification):
        if devel_action == 'nose':
            self._run_nose_tests(notification.object())
            return

        if devel_action == 'devel':
            self._set_up_debug()
        self._set_up_ui()

    def applicationWillTerminate_(self, notification):
        if hasattr(self, 'the_db'):
            self.the_db.close()

    def _run_nose_tests(self, app):
        import runtests
        cb = runtests.main_o()
        cb.add(lambda _ign: app.terminate_(self))

    def _set_up_debug(self):
        Debugging.installPythonExceptionHandler()
        logging.basicConfig(level=logging.INFO)

    def _set_up_ui(self):
        self.the_db = open_db()
        self.the_account = Account(read_config(), self.the_db)
        FolderListing.create(self.foldersPane, self.the_account)
        self.the_account.perform_update()

        def folder_selected(sender, folder):
            MessageListing.create(self.messagesPane, folder)
        signal('ui-folder-selected').connect(folder_selected, weak=False)

        def message_selected(sender, message):
            MessageView.create(self.messageView, message)
        signal('ui-message-selected').connect(message_selected, weak=False)

    @objc.IBAction
    def doSync_(self, sender):
        self.the_account.perform_update()

def open_db():
    import os.path
    from tinymail.localdata import open_local_db
    db_path = os.path.join(os.environ['HOME'], '.tinymail/db.sqlite3')
    return open_local_db(db_path)

def read_config():
    import os
    from os import path
    import json
    cfg_path = path.join(os.environ['HOME'], '.tinymail/account.json')
    with open(cfg_path, 'rb') as f:
        return json.loads(f.read())
