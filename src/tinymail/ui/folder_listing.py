from Foundation import NSObject

class FolderListingItem(NSObject):
    @classmethod
    def itemWithFolder_(cls, folder):
        item = FolderListingItem.new()
        item.folder = folder
        return item

class FolderListingDelegate(NSObject):
    def init(self):
        self.items = []
        return super(FolderListingDelegate, self).init()

    def update_folders(self, folders):
        for item in self.items:
            item.release()
        self.items = [FolderListingItem.itemWithFolder_(f).retain()
                      for f in folders]
        self.outline_view.reloadData()

    def attach_to_view(self, outline_view, selection_changed):
        outline_view.setDataSource_(self)
        outline_view.setDelegate_(self)
        self.outline_view = outline_view
        self.selection_changed = selection_changed

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
        return item.folder.imap_name

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
        self.selection_changed(new_value)
