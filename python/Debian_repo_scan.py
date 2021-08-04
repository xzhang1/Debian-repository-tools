#!/usr/bin/python3

import time
import os
import sys
import apt
import apt_pkg
import requests
import debian.deb822
import string
import subprocess
import logging
from flask import Flask
import argparse
import shutil

app = Flask(__name__)
# DEBUG INFO WARN ERROR CRITICAL
logging.basicConfig(level=logging.WARN)
logger = app.logger

APT_ROOT_DIR = 'apt_root_dir'

def get_aptcache(rootdir):
    '''Construct APT cache based on specified rootpath'''
    print('Update APT cache through folder ', rootdir)
    cache = apt.Cache(rootdir=rootdir)
    ret = cache.update()
    if not ret:
        raise Exception('APT cache update failed')
    cache.open()
    return cache

def construct_repodir(args):
    ''' construct some directoris for repo and temprory files'''
    '''
    basedir
       └── etc
           └── apt
               └── sources.list
    '''
    basedir = os.path.join(args.basedir, APT_ROOT_DIR)
    FileExist = os.path.exists(basedir)
    if FileExist:
        raise Exception('Base dir %s exist, please choose another one.' % basedir)
    FileExist = os.path.exists(args.sources_list)
    if not FileExist:
        raise Exception('Upstream sources file %s not exist' % args.sources_list)
    os.makedirs(basedir)
    os.makedirs(basedir + '/etc/apt/')
    shutil.copyfile(args.sources_list, basedir+'/etc/apt/sources.list')

def clear_repodir(args):
    shutil.rmtree(os.path.join(args.basedir, APT_ROOT_DIR))

def ListBinary(args, cache):
    ''' Get binary package info through python module apt'''
    pkg_list = {}
    for pkg in cache:
        ver_list = []
        vers = pkg.versions
        for ver in vers:
            ver_list.append(ver.version)
        pkg_list[pkg.name] = ver_list
    #print(pkg_list)
    print('Ignore package version, there are', len(pkg_list), 'binary packages.')
    return pkg_list

def ListSource(args, cache):
    ''' Get source package info through python module apt_pkg'''
    pkg_list = {}
    src = apt_pkg.SourceRecords()
    src.restart()
    while src.step():
        if src.package not in pkg_list:
            pkg_list[src.package] = [src.version]
        else:
            pkg_list[src.package].append(src.version)
    #print(pkg_list)
    print('Ignore package version, there are', len(pkg_list), 'source packages.')
    return pkg_list

def ListPkg(args):
    ''' List packages of the Debian repository '''
    print('List packages of the Debian repository')
    print(args)

    if not os.access(args.basedir, os.W_OK):
        print(args.basedir, 'is not write-able.')
        return

    construct_repodir(args)
    cache = get_aptcache(rootdir = os.path.join(args.basedir, APT_ROOT_DIR))
    if args.type == 'binary':
        binary_dict = ListBinary(args, cache)
        clear_repodir(args)
        return binary_dict
    elif args.type == 'source':
        source_dict = ListSource(args, cache)
        clear_repodir(args)
        return source_dict
    else:
        binary_dict = ListBinary(args, cache)
        source_dict = ListSource(args, cache)
        clear_repodir(args)
        return binary_dict, source_dict

def fetch_binary(args, cache):
    ''' Find and fecth a binary package with module apt '''
    try:
        pkg = cache[args.name]
    except: 
        print('Package', args.name, 'not find')
        return

    downloaded = False
    if not args.version:
        pkg.candidate.fetch_binary(destdir=args.destdir)
        print(args.name, pkg.candidate.version, 'been download into', args.destdir)
        downloaded = True
    else:
        vers = pkg.versions
        for ver in vers:
            if ver.version == args.version:
                ver.fetch_binary(destdir=args.destdir)
                print(args.name, args.version, 'been download into', args.destdir)
                downloaded = True

    if not downloaded:
        print('Package', args.name, args.version, 'not find')

def fetch_source(args, cache):
    ''' Find and fetch a source package with apt_pkg '''
    src = apt_pkg.SourceRecords()
    # Search source package from SourceRecords
    source_lookup = src.lookup(args.name)
    while source_lookup:
        if not args.version or args.version == src.version:
            break
        source_lookup = src.lookup(args.name)
    if not source_lookup:
        print('Package', args.name, args.version, 'not find')
        return

    # Here the src.files is a list, each one point to a source file
    # Download those source files one by one with requests
    for file in src.files:
        url = src.index.archive_uri(file.path)
        dest_name = os.path.join(args.destdir, os.path.basename(file.path))
        print('Deonload',os.path.basename(file.path), 'to', args.destdir)
        res = requests.get(url, stream=True)
        with open(dest_name, 'wb') as download_file:
            for chunk in res.iter_content(chunk_size=1024*1024):
                if chunk:
                    download_file.write(chunk)

def FetchPkg(args):
    ''' Fetch package from the Debian repository '''
    print('Fetch package from the Debian repository')
    print(args)

    if not os.access(args.basedir, os.W_OK):
        print(args.basedir, 'is not write-able.')
        return
    if not os.access(args.destdir, os.W_OK):
        print(args.destdir, 'is not write-able.')
        return

    construct_repodir(args)
    cache = get_aptcache(rootdir = os.path.join(args.basedir, APT_ROOT_DIR))
    if args.type == 'binary':
        fetch_binary(args, cache)
    else:
        fetch_source(args, cache)
    clear_repodir(args)

def main():
    print('main')

    parser = argparse.ArgumentParser(add_help=False, description='Debian Repository Scan Tool')
    
    subparsers = parser.add_subparsers(title='Repo Scan Commands:', help='sub-command for repo-scan\n\n')

    list_parser = subparsers.add_parser('list', help='List packages of the upstream repository\n\n')
    list_parser.add_argument('--type', '-t', choices=['binary', 'source', 'all'], help='Package type to be list', required=False, default='all')
    list_parser.set_defaults(handle=ListPkg)

    fetch_parser = subparsers.add_parser('fetch', help='Find and fetch specified package.\n\n')
    fetch_parser.add_argument('--name', '-n', help='Package name', required=True)
    fetch_parser.add_argument('--version', '-v', help='Package version', required=False)
    fetch_parser.add_argument('--type', '-t', choices=['binary', 'source'], help='Package type to be fetched', required=False, default='binary')
    currentdir = os.getcwd()
    fetch_parser.add_argument('--destdir', '-d', help='Where we store the downloaded package file, must be writable.', required=False, default=currentdir)
    fetch_parser.set_defaults(handle=FetchPkg)

    parser.add_argument('--basedir', '-b', help='Folder to store apt meta data, must be writable.', required=False, default='/tmp')
    parser.add_argument('--sources_list', '-s', help='Upstream sources list file, like /etc/apt/souces.list', required=False, default='./sources.list')
    args = parser.parse_args()

    if hasattr(args, 'handle'):
        args.handle(args)
    else:
        parser.print_help()
    
if __name__ == '__main__':
    main()

