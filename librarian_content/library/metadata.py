"""
metadata.py: Handling metadata

Copyright 2014-2015, Outernet Inc.
Some rights reserved.

This software is free software licensed under the terms of GPLv3. See COPYING
file that comes with the source code, or http://www.gnu.org/licenses/gpl.txt.
"""

from __future__ import unicode_literals

import functools
import json
import os

from bottle_utils.lazy import caching_lazy
from outernet_metadata import validator

from librarian_core.utils import to_datetime

from . import adapters
from .base import CDFObject


CONTENT_TYPE_EXTENSIONS = {
    'generic': ['*'],
    'html': ['html', 'htm'],
    'video': ['mp4', 'wmv', 'webm', 'flv', 'ogv'],
    'audio': [],
    'app': [],
    'image': []
}
CONTENT_TYPES = {
    'generic': 1,
    'html': 2,
    'video': 4,
    'audio': 8,
    'app': 16,
    'image': 32,
}
ALIASES = {
    'publisher': ['partner'],
}


class MetadataError(Exception):
    """ Base metadata error """
    def __init__(self, msg, errors):
        self.errors = errors
        super(MetadataError, self).__init__(msg)


class ValidationError(Exception):
    """ Raised when metadata fails validation """
    def __init__(self, path, msg):
        self.path = path
        self.msg = msg
        super(ValidationError, self).__init__(msg)


@caching_lazy
def get_edge_keys():
    """ Return the most recent valid key names.

    :returns:  tuple of strings(key names)"""
    is_deprecated = lambda key: (validator.values.v.deprecated in
                                 validator.values.SPECS[key])
    edge_keys = set()
    for key in validator.values.KEYS:
        if not is_deprecated(key):
            edge_keys.add(key)

    return tuple(edge_keys)


def add_missing_keys(meta):
    """ Make sure metadata dict contains all keys defined in the specification,
    using the default values from the specification itself for missing keys.

    This function modifies the metadata dict in-place, and has no useful return
    value.

    :param meta:    metadata dict
    """
    edge_keys = get_edge_keys()
    for key in edge_keys:
        if key not in meta:
            meta[key] = validator.values.DEFAULTS.get(key, None)


def replace_aliases(meta):
    """ Replace deprecated aliases with their current substitution.

    This function modifies the metadata dict in-place, and has no useful return
    value.

    :param meta:    metadata dict
    """
    edge_keys = get_edge_keys()
    for key in edge_keys:
        if key not in meta:
            for alias in ALIASES.get(key, []):
                if alias in meta:
                    meta[key] = meta.pop(alias)


def clean_keys(meta):
    """ Make sure metadta dict does not have any non-standard keys

    This function modifies the metadata dict in-place, and always returns
    ``None``.

    :param meta:  metadata dict
    """
    edge_keys = get_edge_keys()
    for key in meta.keys():
        if key not in edge_keys:
            del meta[key]


def detect_generation(meta):
    """ Detect metadata generation, if not available try to guess it. """
    try:
        return meta['gen']
    except KeyError:
        for identier_fn in adapters.IDENTIFIERS:
            meta_gen = identier_fn(meta)
            if meta_gen is not None:
                return meta_gen

        raise MetadataError("Unrecognized metadata.",
                            ["Metadata version cannot be detected."])


def upgrade_meta(meta):
    """ Convert metadata structure to latest specification. """
    is_latest = False
    while not is_latest:
        meta_gen = detect_generation(meta)
        try:
            upgrade_fn = adapters.MAP[meta_gen]
        except KeyError:
            is_latest = True
        else:
            upgrade_fn(meta)


def parse_datetime(obj):
    """Recursively discover and attempt to convert strings the may represent a
    datetime object."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                parse_datetime(value)
            else:
                obj[key] = to_datetime(value)
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            if isinstance(value, (dict, list)):
                parse_datetime(value)
            else:
                obj[idx] = to_datetime(value)


def process_meta(meta):
    # attempt bringing metadata up to latest specification before passing it to
    # the validator
    upgrade_meta(meta)
    failed = validator.validate(meta, broadcast=True)
    if failed:
        keys = ', '.join(failed.keys())
        msg = "Metadata validation failed for keys: {0}".format(keys)
        raise MetadataError(msg, failed)
    replace_aliases(meta)
    add_missing_keys(meta)
    clean_keys(meta)
    parse_datetime(meta)
    return meta


def get_meta(basedir, relpath, meta_filenames, encoding='utf8'):
    """Find a meta file at the specified path, read, parse, validate and
    then return it."""
    meta_paths = (os.path.abspath(os.path.join(basedir, relpath, filename))
                  for filename in meta_filenames)
    try:
        (path,) = [path for path in meta_paths if os.path.exists(path)]
    except ValueError:
        raise ValidationError(relpath, 'missing metadata file')
    else:
        try:
            with open(path, 'rb') as f:
                raw_meta = json.load(f, encoding)
                return process_meta(raw_meta)
        except MetadataError as exc:
            raise ValidationError(path, str(exc))
        except (KeyError, ValueError):
            raise ValidationError(path, 'malformed metadata file')
        except (OSError, IOError):
            raise ValidationError(path, 'metadata file cannot be opened')


def determine_content_type(meta):
    """Calculate bitmask of the passed in metadata based on the content types
    found in it."""
    calc = lambda mask, key: mask + CONTENT_TYPES.get(key.lower(), 0)
    return functools.reduce(calc, meta['content'].keys(), 0)


class Meta(CDFObject):
    """ Metadata wrapper with additional methods for easier consumption

    This classed is used as a dict wrapper that provides attrbute access to
    keys, and a few additional properties and methods to ease working with
    metadta.
    """
    DATABASE_NAME = 'content'
    TABLE_NAME = 'content'
    CACHE_KEY_TEMPLATE = u'meta_{0}'
    ATTEMPT_READ_FROM_FILE = False
    ALLOW_EMPTY_INSTANCES = False

    def __init__(self, *args, **kwargs):
        super(Meta, self).__init__(*args, **kwargs)
        self.tags = json.loads(self._data.get('tags') or '{}')

    def __getattr__(self, attr):
        try:
            return self._data[attr]
        except KeyError:
            raise AttributeError("Attribute or key '%s' not found" % attr)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __delitem__(self, key):
        del self._data[key]

    def __contains__(self, key):
        return key in self._data

    def get(self, key, default=None):
        """ Return the value of a metadata or the default value

        This method works exactly the same as ``dict.get()``, except that it
        only works on the keys that exist on the underlying metadata dict.

        :param key:     name of the key to look up
        :param default: default value to use if key is missing
        """
        return self._data.get(key, default)

    @property
    def lang(self):
        return self._data.get('language')

    @property
    def label(self):
        if self._data.get('archive') == 'core':
            return 'core'
        elif self._data.get('is_sponsored'):
            return 'sponsored'
        elif self._data.get('is_partner'):
            return 'partner'
        return 'core'

    @property
    def content_type_names(self):
        """Return list of content type names present in a content object."""
        return [name for (name, cid) in CONTENT_TYPES.items()
                if self._data['content_type'] & cid == cid]

    @classmethod
    def fetch(cls, db, paths):
        query = db.Select(sets=cls.TABLE_NAME, where=db.sqlin('path', paths))
        for row in db.fetchiter(query, paths):
            if row:
                raw_data = cls.row_to_dict(row)
                yield (raw_data['path'], raw_data)
