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

def run_shell_cmd(cmd, logger):
    logger.info(f'[ Run - "{cmd}" ]')
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, shell=True)
        #process.wait()
        outs, errs = process.communicate()
    except:
        process.kill()
        outs, errs = process.communicate()
        exception = sys.exc_info()[1]
        logger.error(f'[ Failed - "{cmd}" ]')
        raise Exception(f'[ Failed - "{cmd}" ]')
    
    for log in outs.strip().split("\n"):
        if log != "":
            logger.debug(log.strip())

    if process.returncode == 0:
        logger.info(f'[ Succeeded - "{cmd}" ]')
    else:
        for log in errs.strip().split("\n"):
            logger.error(log)
        logger.error(f'[ Failed - "{cmd}" ]')
        raise Exception(f'[ Failed - "{cmd}" ]')

    return outs.strip()

def get_dsc(src_name):
    for b_p in cache:
        vers = b_p.versions
        for ver in vers:
            s_name = ver.source_name
            s_version = ver.source_version
            if src_name == s_name:
                print(s_name, s_version)
                # ve.fetch_source(unpack=False, destdir='/tmp/')
                return

def get_deb(deb_name):
    for b_p in cache:
        vers = b_p.versions
        for ver in vers:
            #s_name = ver.source_name
            b_version = ver.version
            if src_name == s_name:
                print(s_name, s_version)
                # ve.fetch_source(unpack=False, destdir='/tmp/')
                return


def construct_repodir(args):
    ''' construct some directoris for repo and temprory files'''
    '''

    │   └── etc
    │       └── apt
    │           └── sources.list
    ├── conf
    │   └── distributions     # real distrbution file of the repository
    └── downloads             # Subdirectory to store downloaded packages
    '''
    basedir = args.basedir
    FileExist = os.path.exists(basedir)
    if FileExist:
        raise Exception('Base dir %s exist, please choose another one.' % basedir)
    FileExist = os.path.exists(args.repo_conf)
    if not FileExist:
        raise Exception('Repo config file %s not exist' % args.repo_conf)
    FileExist = os.path.exists(args.sources_list)
    if not FileExist:
        raise Exception('Upstream sources file %s not exist' % args.sources_list)
    os.makedirs(basedir)
    aptdir = basedir + '/apt-root'
    os.makedirs(aptdir + '/etc/apt/')
    os.makedirs(basedir + '/conf/')
    destdir = basedir + '/downloads/'
    os.makedirs(destdir)
    shutil.copyfile(args.repo_conf, basedir+'/conf/distributions')
    shutil.copyfile(args.sources_list, aptdir+'/etc/apt/sources.list')

def get_pkg_ver(pkg_line):
    # remove comment string/lines
    if -1 == pkg_line.find('#'):
        line = pkg_line[:-1]
    else:
        line = pkg_line[:pkg_line.find('#')]

    if 2 == len(line.split(' ')):
        pkg_name = line.split(' ')[0]
        pkg_ver = line.split(' ')[1]
    elif 1 == len(line.split(' ')):
        pkg_name = line.split(' ')[0]
        pkg_ver = ''
    else:
        pkg_name = pkg_ver = ''
    return pkg_name, pkg_ver

def remove_deb(args):
    print('Remove binary packages...')
    deb_list = args.deb_list
    if not deb_list:
        print('No binary package list file specified. DO NOTHING')
        return
    pkg_list = open(deb_list, 'r')
    destdir = args.basedir + '/downloads/'
    # scan the dsc list
    for pkg_line in pkg_list:
        pkg_name, pkg_ver = get_pkg_ver(pkg_line)
        if '' == pkg_name:
            continue
        #print(pkg_name, pkg_ver)
        base_cmd = 'reprepro -b ' + args.basedir + ' removefilter ' + args.distribution
        if '' == pkg_ver:
            condition = ' \'$PackageType (== deb), Package (== ' + pkg_name + ')\''
        else:
            condition = ' \'$PackageType (== deb), Package (== ' + pkg_name + '), Version (== ' + pkg_ver + ')\''
        #print(base_cmd , condition)
        run_shell_cmd('%s %s' %  (base_cmd, condition), app.logger) 
    pkg_list.close()

def remove_dsc(args):
    print('Remove source packages...')
    dsc_list = args.dsc_list
    if not dsc_list:
        print('No source package list file specified, DO NOTHING..')
        return
    pkg_list = open(dsc_list, 'r')
    destdir = args.basedir + '/downloads/'
    # scan the dsc list
    for pkg_line in pkg_list:
        pkg_name, pkg_ver = get_pkg_ver(pkg_line)
        if '' == pkg_name:
            continue
        #print(pkg_name, pkg_ver)
        base_cmd = 'reprepro -b ' + args.basedir + ' removefilter ' + args.distribution
        if '' == pkg_ver:
            condition = ' \'$PackageType (== dsc), Package (== ' + pkg_name + ')\''
        else:
            condition = ' \'$PackageType (== dsc), Package (== ' + pkg_name + '), Version (== ' + pkg_ver + ')\''
        #print(base_cmd , condition)
        run_shell_cmd('%s %s' %  (base_cmd, condition), app.logger) 
    pkg_list.close()

def add_deb(args, cache):
    print('Add binary packages...')
    deb_list = args.deb_list
    if not deb_list:
        print('No binary package list file specified, DO NOTHING..')
        return
    pkg_list = open(deb_list, 'r')
    destdir = args.basedir + '/downloads/'
    # scan the dsc list
    for pkg_line in pkg_list:
        pkg_name, pkg_ver = get_pkg_ver(pkg_line)
        if '' == pkg_name:
            continue
        #print(pkg_name, pkg_ver)
        pkg = cache[pkg_name]
        if '' == pkg_ver:
            pkg.candidate.fetch_binary(destdir=destdir)
        else:
            vers = pkg.versions
            for ver in vers:
                if ver.version == pkg_ver:
                    ver.fetch_binary(destdir=destdir)
    pkg_list.close()
    for filename in os.listdir(destdir):
        if filename.endswith('.deb'):
            run_shell_cmd('reprepro --basedir %s --component %s includedeb %s %s*.deb' % (args.basedir, args.component, args.distribution, destdir), app.logger) 
            return None

def slow_download(args, cache, pkg_name, pkg_ver):
    print('apt cache can not find source package', pkg_name, 'tend to apt-pkg to make a try', pkg_name)
    destdir = args.basedir + '/downloads/'
    src = apt_pkg.SourceRecords()
    # Search source package from SourceRecords 
    source_lookup = src.lookup(pkg_name)
    while source_lookup:
        if  '' == pkg_ver or pkg_ver == src.version:
            break
        source_lookup = src.lookup(pkg_name)
    if not source_lookup:
        raise ValueError("No source package %s find" % pkg_name)

    # Here the src.files is a list, each one point to a source file
    # Download those source files one by one with requests
    for file in src.files:
        url = src.index.archive_uri(file.path)
        dest_name = os.path.join(destdir, os.path.basename(file.path))
        res = requests.get(url, stream=True)
        with open(dest_name, 'wb') as download_file:
            for chunk in res.iter_content(chunk_size=1024*1024):
                if chunk:
                    download_file.write(chunk)

def add_dsc(args, cache):
    print('Add source packages...')
    dsc_list = args.dsc_list
    if not dsc_list:
        print('No source package list file specified, DO NOTHING..')
        return
    pkg_list = open(dsc_list, 'r')
    destdir = args.basedir + '/downloads/'
    # scan the dsc list
    for pkg_line in pkg_list:
        pkg_name, pkg_ver = get_pkg_ver(pkg_line)
        if '' == pkg_name:
            continue
        #print(pkg_name, pkg_ver)
        src_find = False
        for pkg in cache:
            vers = pkg.versions
            for ver in vers:
                s_name = ver.source_name
                s_ver = ver.version
                if s_name == pkg_name and ('' == pkg_ver or s_ver == pkg_ver):
                    ver.fetch_source(destdir=destdir, unpack=False)
                    src_find = True
                    break 
            if src_find:
                break
        if not src_find:
            slow_download(args, cache, pkg_name, pkg_ver)
    pkg_list.close()

    for filename in os.listdir(destdir):
        if filename.endswith('.dsc'):
            fp = os.path.join(destdir, filename)
            run_shell_cmd('reprepro --basedir %s --component %s includedsc %s %s' % (args.basedir, args.component, args.distribution, fp), app.logger) 

def get_aptcache(rootdir):
    '''Construct APT cache based on specified rootpath'''
    print('Update APT cache through folder ', rootdir)
    cache = apt.Cache(rootdir=rootdir)
    ret = cache.update()
    if not ret:
        raise Exception('APT cache update failed')
    cache.open()
    return cache

def handleCreate(args):
    ''' Create a new repository '''
    print('Create a new repository')
    print(args)
    construct_repodir(args)
    # Handler handleAdd is enough to make all jobs later
    handleAdd(args)

def handleAdd(args):
    ''' Add packages into a repository '''
    print('Add packages into repository')
    print(args.dsc_list)
    cache = get_aptcache(args.basedir + '/apt-root')
    add_deb(args, cache)
    add_dsc(args, cache)
    
def handleRemove(args):
    ''' Remove packages from a repository '''
    print('Rmove packages from repository')
    print(args.deb_list)
    remove_deb(args)
    remove_dsc(args)
    

def main():
    print('main')

    parser = argparse.ArgumentParser(add_help=False, description='Repository management Tool')
    
    subparsers = parser.add_subparsers(title='Repo control Commands:', help='sub-command for repo-ctl\n\n')

    create_parser = subparsers.add_parser('create', help='Create a new repository from zero.\n\n')
    create_parser.add_argument('--deb_list', '-b', help='Binary package list file', required=False)
    create_parser.add_argument('--dsc_list', '-s', help='Source package list file file', required=False)
    create_parser.add_argument('--sources_list', help='Upstream sources list file', required=False, default='./sources.list')
    create_parser.add_argument('--repo_conf', help='config file of the repository', default='./distributions')
    create_parser.set_defaults(handle=handleCreate)

    add_parser = subparsers.add_parser('add', help='Add some packages into a repository.\n\n')
    add_parser.add_argument('--deb_list', '-b',help='Binary package list file', required=False)
    add_parser.add_argument('--dsc_list', '-s', help='Source package list file', required=False)
    add_parser.add_argument('--sources_list', help='Upstream sources list file', required=False, default='./sources.list')
    add_parser.set_defaults(handle=handleAdd)

    remove_parser = subparsers.add_parser('remove', help='Remove some packages from a repository.\n\n')
    remove_parser.add_argument('--deb_list', '-b',help='Binary package list file', required=False)
    remove_parser.add_argument('--dsc_list', '-s', help='Upstream sources list file', required=False)
    remove_parser.set_defaults(handle=handleRemove)

    parser.add_argument('--basedir', help='Location of the reposiory')
    parser.add_argument('--distribution', '-d', help='distribution name', required=False, default='bullseye')
    parser.add_argument('--component', '-c', help='component name', required=False, default='main')
    args = parser.parse_args()

    if hasattr(args, 'handle'):
        args.handle(args)
    else:
        parser.print_help()
    
if __name__ == '__main__':
    main()

