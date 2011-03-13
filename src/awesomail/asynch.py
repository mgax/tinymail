import monocle

class AsynchJob(object):
    def start(self):
        monocle.launch(self.do_stuff)

    @monocle.o
    def do_stuff(self):
        pass
