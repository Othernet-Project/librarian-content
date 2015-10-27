import json
import os
import re
import shutil
import uuid

import scandir

try:
    unicode = unicode
except NameError:
    unicode = str


HEX_PATH = r'(/[0-9a-f]{3}){10}/[0-9a-f]{2}$'  # md5-based dir path
ILLEGAL = re.compile(r'[\s!"#$%&\':()*\-/<=>?@\[\\\]^_`{|},.]+')


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
    for word in ILLEGAL.split(source):
        if word:
            result.append(word)
    return unicode(delim.join(result))


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


def upgrade_meta(meta):
    meta['gen'] = 1
    meta['content'] = {
        'html': {
            'main': meta.pop('index', 'index.html'),
            'keep_formatting': meta.pop('keep_formatting', False)
        }
    }
    for ignored in ('images', 'multipage'):
        meta.pop(ignored, None)


def delete_old_meta(path, meta_filenames):
    if len(meta_filenames) > 1:
        for old_meta_filename in meta_filenames[1:]:
            old_meta_path = os.path.join(path, old_meta_filename)
            if os.path.exists(old_meta_path):
                os.remove(old_meta_path)


def import_content(srcdir, destdir, archive):
    """Discover content directories under ``srcdir`` using the first generation
    folder structure and copy them into ``destdir``, while dropping the old
    nested structure and putting them into a single folder which name is
    generated from the slugified title of the content."""
    meta_filenames = archive.config['meta_filenames']
    for src_path in find_content_dirs(srcdir):
        meta = read_meta(src_path, meta_filenames)
        if not meta:
            continue  # metadata couldn't be found or read, skip this item

        title = (safe_title(meta['title']) or
                 safe_title(meta['url']) or
                 get_random_title())
        dest_path = os.path.join(destdir, title)
        if not os.path.exists(dest_path):
            shutil.copytree(src_path, dest_path)
            upgrade_meta(meta)
            meta_path = os.path.join(dest_path, meta_filenames[0])
            with open(meta_path, 'w') as meta_file:
                json.dump(meta, meta_file)
            # delete any other meta files
            delete_old_meta(dest_path, meta_filenames)
            # add content to database
            content_path = os.path.relpath(dest_path,
                                           archive.config['contentdir'])
            archive.add_to_archive(content_path)
