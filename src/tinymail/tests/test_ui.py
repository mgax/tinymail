import unittest2 as unittest
from monocle import _o
from helpers import mock_db, listen_for, mock_worker, AsyncTestCase

def get_app_delegate():
    import AppKit
    app = AppKit.NSApplication.sharedApplication()
    return app.delegate()

def _account_for_test(config=None):
    from tinymail.account import Account
    if config is None:
        config = {
            'name': 'my test account',
            'host': 'test_host',
            'login_name': 'test_username',
            'login_pass': 'test_password',
        }
    return Account(config, mock_db())

def sleep(delay):
    from PyObjCTools import AppHelper
    from monocle.core import Callback
    cb = Callback()
    AppHelper.callLater(delay, cb, None)
    return cb

def setup_account_controller(account):
    from tinymail.ui_delegates import AccountController
    folders_pane = get_app_delegate().foldersPane
    account_controller = AccountController.newWithAccount_(account)
    get_app_delegate().setAccountController_(account_controller)
    return folders_pane

def setup_folder_controller(folder):
    from tinymail.ui_delegates import FolderController
    app_delegate = get_app_delegate()
    messages_pane = app_delegate.messagesPane
    folder_controller = FolderController.controllerWithFolder_(folder)
    app_delegate.setFolderController_(folder_controller)
    return messages_pane

def cleanup_ui(app_delegate):
    from tinymail.account import Folder
    setup_account_controller(_account_for_test())
    setup_folder_controller(Folder(None, 'f'))

def objc_index_set(values):
    from Foundation import NSMutableIndexSet
    mutable_index_set = NSMutableIndexSet.new()
    for value in values:
        mutable_index_set.addIndex_(value)
    return mutable_index_set

def account_with_folders(**folders):
    account = _account_for_test()
    with mock_worker(**folders):
        account.perform_update()
    return account

class AccountControllerTest(AsyncTestCase):

    def setUp(self):
        from tinymail.ui_delegates import AccountController
        self.imap_data = {'fol1': {}, 'fol2': {}}
        self.account = account_with_folders(**self.imap_data)
        self.folders_pane = setup_account_controller(self.account)

    def tearDown(self):
        cleanup_ui(get_app_delegate())

    def test_show_folders(self):
        cell1 = self.folders_pane.preparedCellAtColumn_row_(0, 0)
        self.assertEqual(cell1.objectValue(), 'fol1')
        cell2 = self.folders_pane.preparedCellAtColumn_row_(0, 1)
        self.assertEqual(cell2.objectValue(), 'fol2')

    def test_folders_updated(self):
        self.imap_data['fol3'] = {}
        with mock_worker(**self.imap_data):
            self.account.perform_update()

        cell1 = self.folders_pane.preparedCellAtColumn_row_(0, 2)
        self.assertEqual(cell1.objectValue(), 'fol3')

    def test_select_folder(self):
        from tinymail.ui_delegates import folder_selected
        with listen_for(folder_selected) as caught_signals:
            self.folders_pane.selectRowIndexes_byExtendingSelection_(
                    objc_index_set([1]), False)

        account_controller = self.folders_pane.delegate()
        self.assertEqual(caught_signals, [
            (account_controller, {'folder': self.account.get_folder('fol2')}),
        ])

class MessageListingTest(AsyncTestCase):

    def setUp(self):
        self.imap_data = {'fol1': {
            6: (6, [r'\Seen'], "From: me\nSubject: test message"),
            8: (8, [r'\Seen'], "From: her\nSubject: another test message"),
        }}
        self.account = account_with_folders(**self.imap_data)
        fol1 = self.account.get_folder('fol1')
        self.messages_pane = setup_folder_controller(fol1)

    def tearDown(self):
        cleanup_ui(get_app_delegate())

    def test_show_messages(self):
        sender1 = self.messages_pane.preparedCellAtColumn_row_(0, 0)
        subject1 = self.messages_pane.preparedCellAtColumn_row_(1, 0)
        self.assertEqual(sender1.objectValue(), "me")
        self.assertEqual(subject1.objectValue(), "test message")

        sender2 = self.messages_pane.preparedCellAtColumn_row_(0, 1)
        subject2 = self.messages_pane.preparedCellAtColumn_row_(1, 1)
        self.assertEqual(sender2.objectValue(), "her")
        self.assertEqual(subject2.objectValue(), "another test message")

    def test_update_messages(self):
        self.imap_data['fol1'][12] = (12, [], "From: other\nSubject: hi")
        with mock_worker(**self.imap_data):
            self.account.perform_update()

        subject1 = self.messages_pane.preparedCellAtColumn_row_(1, 2)
        self.assertEqual(subject1.objectValue(), "hi")

    def test_select_message(self):
        from tinymail.ui_delegates import message_selected

        with listen_for(message_selected) as caught_signals:
            self.messages_pane.selectRowIndexes_byExtendingSelection_(
                    objc_index_set([1]), False)

        fol1 = self.account.get_folder('fol1')
        folder_controller = self.messages_pane.delegate()
        self.assertEqual(caught_signals, [
            (folder_controller, {'message': fol1.get_message(8)}),
        ])
        self.assertEqual(list(folder_controller.get_selected_messages()),
                         [fol1.get_message(8)])
