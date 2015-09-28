"""
content.py: Low-level content asset management

Copyright 2014-2015, Outernet Inc.
Some rights reserved.

This software is free software licensed under the terms of GPLv3. See COPYING
file that comes with the source code, or http://www.gnu.org/licenses/gpl.txt.
"""

import json
import os

import scandir

from . import metadata


class ValidationError(Exception):
    """ Raised when zipball fails validation """
    def __init__(self, path, msg):
        self.path = path
        self.msg = msg
        super(ValidationError, self).__init__(msg)


def filewalk(basedir):
    """Discover and yield all files found in `basedir`"""
    for entry in scandir.scandir(basedir):
        if entry.is_dir():
            for child in filewalk(entry.path):
                yield child
        else:
            yield entry.path


def find_content_dirs(basedir, meta_filename='.contentinfo', relative=True):
    """Find all content directories within basedir"""
    for path in filewalk(basedir):
        if os.path.basename(path) == meta_filename:
            content_path = os.path.dirname(path)
            if relative:
                yield os.path.relpath(content_path, basedir)
            else:
                yield content_path


def get_meta(basedir, relpath, meta_filename='.contentinfo', encoding='utf8'):
    """Find `meta_filename` at the specified path, read, parse, validate and
    then return it."""
    path = os.path.abspath(os.path.join(basedir, relpath, meta_filename))
    try:
        with open(path, 'rb') as f:
            raw_meta = json.load(f, encoding)
            return metadata.process_meta(raw_meta)
    except metadata.MetadataError as exc:
        raise ValidationError(path, str(exc))
    except (KeyError, ValueError):
        raise ValidationError(path, 'missing or malformed metadata file')
    except (OSError, IOError):
        raise ValidationError(path, 'metadata file cannot be opened')


def get_content_size(basedir, relpath):
    """Return the size of the content folder matching the given path."""
    content_path = os.path.join(basedir, relpath)
    return sum([os.stat(filepath).st_size
                for filepath in filewalk(content_path)])