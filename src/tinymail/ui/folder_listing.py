from Foundation import NSObject

class FolderListingItem(NSObject):
    @classmethod
    def itemWithString_(cls, value):
        i = FolderListingItem.new()
        i.value = value
        return i

class FolderListingDataSource(NSObject):
    @classmethod
    def sourceWithFolderPaths_selectionChanged_(cls,
            folder_paths, selection_changed):
        s = cls.new()
        #s.folder_paths = folder_paths
        s.items = [FolderListingItem.itemWithString_(p).retain()
                   for p in folder_paths]
        s.selection_changed = selection_changed
        return s

    def outlineView_numberOfChildrenOfItem_(self, outline_view, item):
        #print "outlineView_numberOfChildrenOfItem_(%r) called" % item
        assert item is None
        return len(self.items)

    def outlineView_isItemExpandable_(self, outline_view, item):
        #print "outlineView_isItemExpandable_(%r) called" % item
        assert isinstance(item, FolderListingItem)
        return False

    def outlineView_child_ofItem_(self, outline_view, child, item):
        #print "outlineView_child_ofItem(%r, %r)_ called" % (child, item)
        assert item is None
        assert -1 < child < len(self.items)
        output = self.items[child]
        #print 'returning %r' % output
        return output

    def outlineView_objectValueForTableColumn_byItem_(self, outline_view,
                                                      tableColumn, item):
        #print ("outlineView_objectValueForTableColumn_byItem_(%r, %r) called"
        #       % (tableColumn, item))
        assert isinstance(item, FolderListingItem)
        return item.value

    def outlineView_shouldEditTableColumn_item_(self, outline_view,
                                                tableColumn, item):
        #print ("outlineView_shouldEditTableColumn_item_(%r, %r) called"
        #       % (tableColumn, item))
        return False

    def outlineViewSelectionDidChange_(self, notification):
        outline_view = notification.object()
        row = outline_view.selectedRow()
        new_value = (None if row == -1 else outline_view.itemAtRow_(row).value)
        self.selection_changed(new_value)

def set_up_folder_listing(imap_conn, folders_tree, selection_changed):
    from tinymail.ui.folder_listing import FolderListingDataSource
    folder_paths = list(imap_conn.get_mailboxes())
    ds = FolderListingDataSource.sourceWithFolderPaths_selectionChanged_(
                folder_paths, selection_changed)
    folders_tree.setDataSource_(ds)
    folders_tree.setDelegate_(ds)
