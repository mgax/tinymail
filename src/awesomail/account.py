class Account(object):
    def list_folders(self):
        return self._folders.itervalues()

    def get_folder(self, name):
        return self._folders[name]

class Folder(object):
    def list_messages(self):
        return self._messages.itervalues()
