import logging
import monocle

log = logging.getLogger(__name__)

class AsynchJob(object):
    failure = None

    @monocle.o
    def start(self):
        try:
            yield self.do_stuff()
        except Exception, e:
            self.failure = e
            log.exception("Error in asynch job")

    @monocle.o
    def do_stuff(self):
        pass
