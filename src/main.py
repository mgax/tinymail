def load_python_stuff():
    import sys

    if len(sys.argv) > 1 and sys.argv[1] in ('devel', 'nose'):
        sys.path[0:0] = ['src', 'sandbox/lib/python2.6/site-packages']
        devel_action = sys.argv[1]

    else:
        devel_action = None

    import tinymail.ui_delegates
    tinymail.ui_delegates.devel_action = devel_action

def main():
    load_python_stuff()

    from PyObjCTools import AppHelper
    AppHelper.runEventLoop()

if __name__ == '__main__':
    main()
