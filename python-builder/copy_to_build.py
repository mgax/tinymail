#!/usr/bin/python

""" Copy python packages during build. """

import sys
import os
from os import path
import shutil

def copy_tree(src_dir_path, dst_dir_path, name):
    print "copying %r" % name
    src_path = path.join(src_dir_path, name)
    dst_path = path.join(dst_dir_path, name)
    if path.isdir(dst_path):
        shutil.rmtree(dst_path)
    shutil.copytree(src_path, dst_path)

def main(build_path):
    project_path = path.abspath(path.join(path.dirname(__file__), '..'))

    copy_tree(path.join(project_path, 'src'), build_path, 'tinymail')

    deps_path = path.join(project_path, 'python-builder/deps')
    for name in os.listdir(deps_path):
        copy_tree(deps_path, build_path, name)

if __name__ == '__main__':
    if len(sys.argv) == 2:
        main(sys.argv[1])
    else:
        print "Usage: %s <build_path>" % sys.argv[0]
