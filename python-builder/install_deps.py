#!/usr/bin/python

""" Install dependencies for tinymail in a local folder. """

dependencies = [
    {'package_name': 'monocle',
     'setuptools': True,
     'md5': "b5533d4687af7b175594b0efedc06f63",
     'url': ("http://pypi.python.org/packages/source/"
             "m/monocle/monocle-0.11.tar.gz")},
    {'package_name': 'blinker',
     'setuptools': False,
     'md5': "b93962f6b0d854a9659d397db2a7894d",
     'url': ("http://pypi.python.org/packages/source/"
             "b/blinker/blinker-1.1.zip")},
]

import sys
import subprocess
import os
from os import path
import tempfile
import shutil
import urllib
import hashlib

def download_to(url, folder_path):
    file_name = url.rsplit('/', 1)[1]
    download_path = path.join(folder_path, file_name)
    got_path, headers = urllib.urlretrieve(url, download_path)
    return file_name

def verify(file_path, md5sum):
    checksum = hashlib.md5()
    with open(file_path, 'rb') as f:
        while True:
            buf = f.read(2**16)
            if not buf:
                break
            checksum.update(buf)
    if checksum.hexdigest() != md5sum:
        raise ValueError("Checksum failed for %r")

def install(package, build_path, install_path):
    archive_name = download_to(package['url'], build_path)
    verify(path.join(build_path, archive_name), package['md5'])

    dev_null = open('/dev/null', 'wb')

    tgz_ext = '.tar.gz'
    zip_ext = '.zip'
    if archive_name.endswith(tgz_ext):
        subprocess.check_call(['tar', 'xzf', archive_name],
                              cwd=build_path, stdout=dev_null, stderr=dev_null)
        dist_path = path.join(build_path, archive_name[:-len(tgz_ext)])

    elif archive_name.endswith(zip_ext):
        subprocess.check_call(['unzip', archive_name],
                              cwd=build_path, stdout=dev_null, stderr=dev_null)
        dist_path = path.join(build_path, archive_name[:-len(zip_ext)])

    else:
        raise ValueError("Unknown archive format: %r" % archive_name)

    cmd = [sys.executable, 'setup.py', 'install', '--root='+install_path]
    if package['setuptools']:
        cmd.append('--single-version-externally-managed')
    subprocess.check_call(cmd, cwd=dist_path, stdout=dev_null, stderr=dev_null)

def main():
    deps_path = path.join(path.abspath(path.dirname(__file__)), 'deps')
    if not path.isdir(deps_path):
        os.mkdir(deps_path)

    temp_path = tempfile.mkdtemp()
    try:
        build_path = path.join(temp_path, 'build')
        os.mkdir(build_path)

        for package in dependencies:
            package_name = package['package_name']
            dest_path = path.join(deps_path, package_name)
            if path.isdir(dest_path):
                print "Skipping %r, it's already installed" % package_name
            else:
                install(package, build_path, temp_path)
                site_pkg = 'Library/Python/2.6/site-packages'
                install_path = path.join(temp_path, site_pkg, package_name)
                shutil.copytree(install_path, dest_path)
                print "Installed %r" % dest_path

    finally:
        shutil.rmtree(temp_path)

if __name__ == '__main__':
    main()
