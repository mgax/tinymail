import logging
import email
import objc
from Foundation import NSObject, NSURL, NSString, NSISOLatin1StringEncoding
import AppKit
from PyObjCTools import Debugging
from blinker import signal
from tinymail.account import Account
from tinymail.tests.test_localdata import make_test_db as demo_db

_signals = [signal(name) for name in
            ('ui-folder-selected', 'ui-message-selected')]


class FolderListingItem(NSObject):
    @classmethod
    def itemWithFolder_(cls, folder):
        item = FolderListingItem.new()
        item.folder = folder
        return item


class FolderListingDelegate(NSObject):
    @classmethod
    def create(cls, outline_view, account):
        self = cls.new()
        self.outline_view = outline_view
        outline_view.setDataSource_(self)
        outline_view.setDelegate_(self)
        self.cb = lambda a: self.handle_folders_updated(a)
        signal('account-updated').connect(self.cb)
        sel = self.handle_folders_updated
        return self

    def init(self):
        self.items = []
        return super(FolderListingDelegate, self).init()

    def handle_folders_updated(self, account):
        for item in self.items:
            item.release()
        self.items = [FolderListingItem.itemWithFolder_(f).retain()
                      for f in account._folders.values()]
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

        signal('ui-folder-selected').send(new_value)


class MessageListingDelegate(NSObject):
    @classmethod
    def create(cls, table_view):
        self = cls.new()
        self.table_view = table_view
        table_view.setDelegate_(self)
        table_view.setDataSource_(self)
        self._set_up_columns()
        self.cb1 = lambda f: self.handle_folder_selected(f)
        signal('ui-folder-selected').connect(self.cb1)
        self.cb = lambda f: self.handle_messages_updated(f)
        signal('folder-updated').connect(self.cb)
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
        return super(MessageListingDelegate, self).init()

    def handle_folder_selected(self, folder):
        if self._folder is not None:
            pass

        self._folder = folder
        if self._folder is None:
            self.messages_updated({})
            return

        self.messages_updated(self._folder._messages)

    def handle_messages_updated(self, folder):
        if folder is not self._folder:
            return
        self.messages_updated(folder._messages)

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

        signal('ui-message-selected').send(new_value)


class MessageViewDelegate(NSObject):
    @classmethod
    def create(cls, web_view):
        self = cls.new()
        self.web_view = web_view
        self._message = None
        self.cb1 = lambda m: self.handle_message_selected(m)
        signal('ui-message-selected').connect(self.cb1)
        self.cb = lambda m: self.handle_message_updated(m)
        signal('message-updated').connect(self.cb)
        return self

    def _configure_web_view(self):
        web_view_prefs = self.web_view.preferences()
        web_view_prefs.setJavaEnabled_(False)
        web_view_prefs.setJavaScriptEnabled_(False)
        web_view_prefs.setPluginsEnabled_(False)
        web_view_prefs.setUsesPageCache_(False)

    def handle_message_selected(self, message):
        self._message = message
        if self._message is None:
            self._update_view_with_string("")
            return

        self._update_view_with_string("Loading...")
        self._displayed = False
        if self._message.raw_full is None:
            self._message.load_full()
        else:
            self.handle_full_message(self._message, self._message.raw_full)

    def handle_message_updated(self, message):
        if self._message is not message:
            return
        self.handle_full_message(message, message.raw_full)

    def handle_full_message(self, message, mime):
        assert message is self._message, ('%r is not %r' %
                                (message.imap_id, self._message.imap_id))
        if self._displayed:
            return
        self._displayed = True
        self._update_view_with_string(raw_full)

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
        self._set_up_debug()
        self.the_account = Account(read_config(), demo_db())
        self._set_up_ui()
        self.the_account.perform_update()

    def _set_up_debug(self):
        Debugging.installPythonExceptionHandler()
        logging.basicConfig(level=logging.INFO)

    def _set_up_ui(self):
        FolderListingDelegate.create(self.foldersPane, self.the_account)
        MessageListingDelegate.create(self.messagesPane)
        MessageViewDelegate.create(self.messageView)

    @objc.IBAction
    def doSync_(self, sender):
        self.the_account.sync_folders()

def read_config():
    import os
    from os import path
    import json
    cfg_path = path.join(os.environ['HOME'], '.tinymail/account.json')
    with open(cfg_path, 'rb') as f:
        return json.loads(f.read())
