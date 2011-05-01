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
    def tearDown(self):
        cleanup_ui(get_app_delegate())

    def test_show_folders(self):
        from tinymail.ui_delegates import AccountController
        account = account_with_folders(fol1={6: None, 8: None}, fol2={})
        folders_pane = setup_account_controller(account)

        cell1 = folders_pane.preparedCellAtColumn_row_(0, 0)
        self.assertEqual(cell1.objectValue(), 'fol1')
        cell2 = folders_pane.preparedCellAtColumn_row_(0, 1)
        self.assertEqual(cell2.objectValue(), 'fol2')

    def test_folders_updated(self):
        from tinymail.ui_delegates import AccountController
        account = account_with_folders()
        folders_pane = setup_account_controller(account)

        with mock_worker(fol2={}, fol3={}):
            account.perform_update()

        cell1 = folders_pane.preparedCellAtColumn_row_(0, 0)
        self.assertEqual(cell1.objectValue(), 'fol2')
        cell2 = folders_pane.preparedCellAtColumn_row_(0, 1)
        self.assertEqual(cell2.objectValue(), 'fol3')

    def test_select_folder(self):
        from tinymail.ui_delegates import AccountController, folder_selected
        account = account_with_folders(fol1={6: None, 8: None}, fol2={})
        folders_pane = setup_account_controller(account)
        account_controller = folders_pane.delegate()

        with listen_for(folder_selected) as caught_signals:
            rows = objc_index_set([1])
            folders_pane.selectRowIndexes_byExtendingSelection_(rows, False)

        self.assertEqual(caught_signals, [
            (account_controller, {'folder': account.get_folder('fol2')}),
        ])

class MessageListingTest(AsyncTestCase):
    def tearDown(self):
        cleanup_ui(get_app_delegate())

    def test_show_messages(self):
        msg6 = (6, [r'\Seen'], "From: me\nSubject: test message")
        msg8 = (8, [r'\Seen'], "From: her\nSubject: another test message")
        account = account_with_folders(fol1={6: msg6, 8: msg8})
        messages_pane = setup_folder_controller(account.get_folder('fol1'))

        sender1 = messages_pane.preparedCellAtColumn_row_(0, 0)
        subject1 = messages_pane.preparedCellAtColumn_row_(1, 0)
        self.assertEqual(sender1.objectValue(), "me")
        self.assertEqual(subject1.objectValue(), "test message")

        sender2 = messages_pane.preparedCellAtColumn_row_(0, 1)
        subject2 = messages_pane.preparedCellAtColumn_row_(1, 1)
        self.assertEqual(sender2.objectValue(), "her")
        self.assertEqual(subject2.objectValue(), "another test message")

    def test_update_messages(self):
        msg6 = (6, [r'\Seen'], "From: me\nSubject: test message")
        msg8 = (8, [r'\Seen'], "From: her\nSubject: another test message")
        account = account_with_folders(fol1={})
        messages_pane = setup_folder_controller(account.get_folder('fol1'))

        with mock_worker(fol1={6: msg6, 8: msg8}):
            account.perform_update()

        subject1 = messages_pane.preparedCellAtColumn_row_(1, 0)
        self.assertEqual(subject1.objectValue(), "test message")

        subject2 = messages_pane.preparedCellAtColumn_row_(1, 1)
        self.assertEqual(subject2.objectValue(), "another test message")

    def test_select_message(self):
        from tinymail.ui_delegates import message_selected
        msg6 = (6, [r'\Seen'], "From: me\nSubject: test message")
        msg8 = (8, [r'\Seen'], "From: her\nSubject: another test message")
        account = account_with_folders(fol1={6: msg6, 8: msg8})
        fol1 = account.get_folder('fol1')
        messages_pane = setup_folder_controller(account.get_folder('fol1'))
        folder_controller = messages_pane.delegate()

        with listen_for(message_selected) as caught_signals:
            rows = objc_index_set([1])
            messages_pane.selectRowIndexes_byExtendingSelection_(rows, False)

        self.assertEqual(caught_signals, [
            (folder_controller, {'message': fol1.get_message(8)}),
        ])
