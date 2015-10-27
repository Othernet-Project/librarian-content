import os
import re
import shutil
import unicodedata
import uuid

import scandir

from .library.metadata import get_meta, ValidationError

try:
    unicode = unicode
except NameError:
    unicode = str


HEX_PATH = r'(/[0-9a-f]{3}){10}/[0-9a-f]{2}$'  # md5-based dir path
PUNCT = re.compile(r'[^a-zA-Z0-9]+')


def fnwalk(path, fn, shallow=False):
    """
    Walk directory tree top-down until directories of desired length are found
    This generator function takes a ``path`` from which to begin the traversal,
    and a ``fn`` object that selects the paths to be returned. It calls
    ``os.listdir()`` recursively until either a full path is flagged by ``fn``
    function as valid (by returning a truthy value) or ``os.listdir()`` fails
    with ``OSError``.
    This function has been added specifically to deal with large and deep
    directory trees, and it's therefore not advisable to convert the return
    values to lists and similar memory-intensive objects.
    The ``shallow`` flag is used to terminate further recursion on match. If
    ``shallow`` is ``False``, recursion continues even after a path is matched.
    For example, given a path ``/foo/bar/bar``, and a matcher that matches
    ``bar``, with ``shallow`` flag set to ``True``, only ``/foo/bar`` is
    matched. Otherwise, both ``/foo/bar`` and ``/foo/bar/bar`` are matched.
    """
    if fn(path):
        yield path
        if shallow:
            return

    try:
        entries = scandir.scandir(path)
    except OSError:
        return

    for entry in entries:
        if entry.is_dir():
            for child in fnwalk(entry.path, fn, shallow):
                yield child


def find_content_dirs(basedir):
    """ Find all content directories within basedir
    This function matches all MD5-based directory structures within the
    specified base directory. It uses glob patterns to do this.
    The returned value is an iterator. It's highly recommended to use it as is
    (e.g., without converting it to a list) due to increased memory usage with
    large number of directories.
    """
    rxp = re.compile(basedir + HEX_PATH)
    for path in fnwalk(basedir, lambda p: rxp.match(p)):
        yield path


def get_random_title():
    return uuid.uuid4().hex


def safe_title(source, delim=u' '):
    result = []
    for word in PUNCT.split(source):
        word = unicodedata.normalize('NFKD', word).encode('ascii', 'ignore')
        if word:
            result.append(word)
    return unicode(delim.join(result))


def import_content(srcdir, destdir, meta_filenames):
    """Discover content directories under ``srcdir`` using the first generation
    folder structure and copy them into ``destdir``, while dropping the old
    nested structure and putting them into a single folder which name is
    generated from the slugified title of the content."""
    for src_path in find_content_dirs(srcdir):
        content_path = os.path.relpath(src_path, srcdir)
        try:
            meta = get_meta(srcdir, content_path, meta_filenames)
        except ValidationError:
            continue
        else:
            title = (safe_title(meta['title']) or
                     safe_title(meta['url']) or
                     get_random_title())
            dest_path = os.path.join(destdir, title)
            if not os.path.exists(dest_path):
                shutil.copytree(src_path, dest_path)
