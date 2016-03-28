import functools
import itertools
import json
import logging
import os

import gevent
import scandir

from bottle_utils.common import basestring
from bs4 import BeautifulSoup

from librarian_core.exts import ext_container


HTML_NAMES = ['index', 'main', 'start']
HTML_EXTENSIONS = ['html', 'htm', 'xhtml']
HTML_FILENAMES = map('.'.join, itertools.product(HTML_NAMES, HTML_EXTENSIONS))
META_FILENAMES = ('info.json', '.contentinfo')
REQUIRED_KEYS = {
    'title': 'title',
    'description': 'description',
    'copyright': 'license',
    'language': 'language',
    'keywords': 'keywords',
    'author': 'publisher',
    'outernet_formatting': ('content', 'keep_formatting'),
}


def find_content_dirs(basedir, meta_filenames, sleep_interval=0.01):
    for entry in scandir.scandir(basedir):
        if entry.is_dir():
            for child in find_content_dirs(entry.path, meta_filenames):
                yield child
        else:
            filename = os.path.basename(entry.path)
            if filename in meta_filenames:
                yield os.path.dirname(entry.path)
    # force context switch
    gevent.sleep(sleep_interval)


def find_html(basedir, meta):
    # attempt to use html file preferred by metadata
    try:
        return meta['content']['main']
    except KeyError:
        pass  # not specified in meta
    # if metadata did not specify any, attempt finding one of the
    # preferred files
    for candidate in HTML_FILENAMES:
        filename = os.path.join(basedir, candidate)
        if os.path.exists(filename):
            return filename
    # if no preferred file was found, find any html file within basedir
    for (dirpath, dirnames, filenames) in scandir.walk(basedir):
        for candidate in filenames:
            (name, ext) = os.path.splitext(candidate)
            if ext in HTML_EXTENSIONS:
                return os.path.join(dirpath, candidate)


def read_meta(basedir, meta_filenames):
    meta = None
    for filename in meta_filenames:
        meta_path = os.path.join(basedir, filename)
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r') as meta_file:
                    meta = json.load(meta_file)
            except Exception:
                continue

    return meta


def inject_meta(meta, html_path, encoding='utf-8'):
    # read source html
    with open(html_path, 'r') as html_in:
        soup = BeautifulSoup(html_in.read(), "html.parser")
    # inject meta tags into existing structure
    head = soup.find('head')
    for (dest_key, key_seq) in REQUIRED_KEYS.items():
        key_seq = [key_seq] if isinstance(key_seq, basestring) else key_seq
        try:
            value = functools.reduce(lambda src, key: src[key], key_seq, meta)
        except KeyError:
            # key not found in metadata, just skip it
            continue
        else:
            meta_tag = soup.new_tag('meta')
            meta_tag[dest_key] = value
            head.insert(1, meta_tag)
    # export soup structure into raw string
    raw_html = soup.prettify(encoding)
    # write html back into the same file
    with open(html_path, 'wb') as html_out:
        html_out.write(raw_html)


def meta2html(srcdir):
    srcdir = os.path.abspath(srcdir)
    if not os.path.exists(srcdir):
        logging.info(u"Content directory: {} does not exist.".format(srcdir))
        return

    for src_path in find_content_dirs(srcdir, META_FILENAMES):
        meta = read_meta(src_path, META_FILENAMES)
        if not meta:
            logging.error(u"No valid metadata found in {}".format(src_path))
            continue  # metadata couldn't be found or read, skip this item

        html_path = find_html(src_path, meta)
        if not html_path:
            logging.error(u"No valid html file found in {}".format(src_path))
            continue  # no html file was found where results could be written

        inject_meta(meta, html_path)


def up(db, conf):
    (success, base_paths) = ext_container.fsal.list_base_paths()
    for srcdir in base_paths:
        meta2html(srcdir)
