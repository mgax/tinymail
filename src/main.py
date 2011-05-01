def load_python_stuff():
    import sys, os

    if len(sys.argv) > 1:
        config_path = sys.argv[1]
        del sys.argv[1]
    else:
        config_path = os.path.join(os.environ['HOME'], '.tinymail')

    startup_path = os.path.join(config_path, 'startup.py')
    if os.path.isfile(startup_path):
        with open(startup_path, 'rb') as f:
            exec(f.read())

    import tinymail.ui_delegates
    tinymail.ui_delegates.config_path = config_path

def main():
    load_python_stuff()

    from PyObjCTools import AppHelper
    AppHelper.runEventLoop()

if __name__ == '__main__':
    main()
