"""
archive.py: Download handling

Copyright 2014-2015, Outernet Inc.
Some rights reserved.

This software is free software licensed under the terms of GPLv3. See COPYING
file that comes with the source code, or http://www.gnu.org/licenses/gpl.txt.
"""

import logging
import os

from librarian_core.utils import utcnow

from . import metadata
from .utils import to_list


class Archive(object):

    def __init__(self, backend):
        name = BaseArchive.__name__

        if not isinstance(backend, BaseArchive):
            raise TypeError('arg 1 must be an instance of {0}'.format(name))

        if not hasattr(backend, '_{0}__initialized'.format(name)):
            msg = ("{0} not initialized. Make sure the __init__ function of "
                   "the superclass is invoked.".format(name))
            raise RuntimeError(msg)

        object.__setattr__(self, 'backend', backend)

    def __getattribute__(self, name):
        backend = object.__getattribute__(self, 'backend')
        return getattr(backend, name)

    def __setattr__(self, name, value):
        backend = object.__getattribute__(self, 'backend')
        setattr(backend, name, value)

    @staticmethod
    def get_backend_class(backend_path):
        splitted = backend_path.split('.')
        backend_cls_name = splitted[-1]
        try:
            # try loading from pythonpath
            mod = __import__(backend_path, fromlist=[backend_cls_name])
        except ImportError:
            # backend not on pythonpath, try loading it from local package
            from . import backends
            backend_path = '.'.join([backends.__name__] + splitted[:-1])
            mod = __import__(backend_path, fromlist=[backend_cls_name])

        return getattr(mod, backend_cls_name)

    @classmethod
    def setup(cls, backend_path, *args, **kwargs):
        backend_cls = cls.get_backend_class(backend_path)
        backend = backend_cls(*args, **kwargs)
        return cls(backend)


class BaseArchive(object):

    required_config_params = (
        'contentdir',
        'meta_filenames',
    )
    # list of content types that cannot be displayed on the mixed content list
    # where all other types are mixed together
    exclude_from_content_list = (
        'app',
    )
    # list of content types which data needs to be completely fetched even when
    # loading the content list
    prefetchable_types = (
        'app',
    )

    def __init__(self, fsal, **config):
        self.fsal = fsal
        self.config = config
        for key in self.required_config_params:
            if key not in self.config:
                raise TypeError("{0}.__init__() needs keyword-only argument "
                                "{1}".format(type(self).__name__, key))

        self.__initialized = True

    def get_count(self, terms=None, tag=None, lang=None, content_type=None):
        """Return the number of matching content metadata filtered by the given
        options.
        Implementation is backend specific.

        :param terms:         string: search query
        :param tag:           list of string tags
        :param lang:          string: language code
        :param content_type:  int: content type id"""
        raise NotImplementedError()

    def get_content(self, terms=None, offset=0, limit=0, tag=None, lang=None,
                    content_type=None):
        """Return iterable of matching content metadata filtered by the given
        options.
        Implementation is backend specific.

        :param terms:         string: search query
        :param offset:        int: start index
        :param limit:         int: max number of items to be returned
        :param tag:           list of string tags
        :param lang:          string: language code
        :param content_type:  int: content type id"""
        raise NotImplementedError()

    def get_single(self, relpath):
        """Return a single metadata object matching the given content path.
        Implementation is backend specific.

        :param relpath:  Relative path of content"""
        raise NotImplementedError()

    def get_multiple(self, relpaths, fields=None):
        """Return iterable of matching content metadatas by the given list of
        content paths.
        Implementation is backend specific.

        :param relpaths:  iterable of relative content paths to be found
        :param fields:    list of fields to be fetched (defaults to all)"""
        raise NotImplementedError()

    def content_for_domain(self, domain):
        """Return iterable of content metadata partially matching the specified
        domain.
        Implementation is backend specific.

        :param domain:  string
        :returns:       iterable of matched contents"""
        raise NotImplementedError()

    def add_meta_to_db(self, meta):
        """Add the passed in content metadata to the database.
        Implementation is backend specific.

        :param metadata:  Dictionary of valid content metadata"""
        raise NotImplementedError()

    def remove_meta_from_db(self, relpath):
        """Remove the specified content's metadata from the database.
        Implementation is backend specific.

        :param relpath:  Relative path of content that is about to be deleted
        """
        raise NotImplementedError()

    def add_replacement_data(self, metas, needed_keys, key_prefix='replaces_'):
        """Modify inplace the list of passed in metadata dicts by adding the
        needed data about the content that is about to be replaced to the new
        meta information, with it's keys prefixed by the specified string.
        [{
            'path': '/some/where',
            'title': 'first',
            'replaces': '/this/there',
            ...
        }, {
            'path': 'abc',
            'title': 'second',
            ...
        }]

        Will be turned into:

        [{
            'path': '/some/where',
            'title': 'first',
            'replaces': '/this/there',
            'replaces_title': 'old content title',
             ...
        }, {
            'path': 'abc',
            'title': 'second',
            ...
        }]
        """
        replaceable_paths = [meta['replaces'] for meta in metas
                             if meta.get('replaces') is not None]
        if not replaceable_paths:
            return

        needed_fields = tuple(sorted(set(tuple(needed_keys) + ('path',))))
        replaceables = self.get_multiple(replaceable_paths,
                                         fields=needed_fields)
        get_needed_data = lambda d: dict((key, d[key]) for key in needed_keys)
        replaceable_metas = dict((data['path'], get_needed_data(data))
                                 for data in replaceables)
        for meta in metas:
            if meta.get('replaces') in replaceable_metas:
                replaceable_metadata = replaceable_metas[meta['replaces']]
                for key in needed_keys:
                    replace_key = '{0}{1}'.format(key_prefix, key)
                    meta[replace_key] = replaceable_metadata[key]

    def delete_content_files(self, relpath):
        """Delete the specified content's directory and all of it's files.

        :param relpath:  Relative path of content which is about to be deleted
        :returns:        bool: indicating success of deletion"""
        try:
            self.fsal.remove(relpath)
        except Exception as exc:
            logging.debug(u"Deletion of '{0}' failed: '{1}'".format(relpath,
                                                                    exc))
            return False
        else:
            return True

    def __add_auto_fields(self, meta, relpath):
        # add auto-generated values to metadata before writing into db
        meta['path'] = relpath
        meta['updated'] = utcnow()
        (success, dir_fso) = self.fsal.get_fso(relpath)
        # TODO: should we raise in this case?
        meta['size'] = dir_fso.size if success else 0
        meta['content_type'] = metadata.determine_content_type(meta)
        # if cover or thumb images do not exist, avoid later filesystem lookups
        # by not writing the default paths into the storage
        for key in ('cover', 'thumb'):
            filename = meta.get(key)
            if filename:
                file_path = os.path.join(relpath, filename)
                if not self.fsal.exists(file_path):
                    meta.pop(key, None)

    def __add_to_archive(self, relpath):
        logging.debug(u"Adding content '{0}' to archive.".format(relpath))
        meta_filenames = self.config['meta_filenames']
        contentdir = self.config['contentdir']
        try:
            meta = metadata.get_meta(contentdir, relpath, meta_filenames)
        except metadata.ValidationError as exc:
            msg = u"Metadata of '{0}' is invalid: '{1}'".format(relpath, exc)
            logging.debug(msg)
            return False
        else:
            self.__add_auto_fields(meta, relpath)
            return self.add_meta_to_db(meta)

    @to_list
    def add_to_archive(self, relpaths):
        """Add the specified content item(s) to the library.
        Adds the meta information of the content item to the database.

        :param relpaths:  string: a single content path to be added
                          iterable: an iterable of content paths to be added
        :returns:         int: successfully added content count
        """
        return sum([self.__add_to_archive(path) for path in relpaths])

    def __remove_from_archive(self, relpath):
        msg = u"Removing content '{0}' from archive.".format(relpath)
        logging.debug(msg)
        self.delete_content_files(relpath)
        return self.remove_meta_from_db(relpath)

    @to_list
    def remove_from_archive(self, relpaths):
        """Removes the specified content(s) from the library.
        Deletes the matching content files from `contentdir` and removes their
        meta information from the database.

        :param relpaths:  string: a single content path to be removed
                          iterable: an iterable of content paths to be removed
        :returns:         int: successfully removed content count"""
        return sum([self.__remove_from_archive(path) for path in relpaths])

    def find_content_dirs(self, relative=True):
        """Find all content directories within basedir"""
        meta_filenames = self.config['meta_filenames']
        query = ' '.join(meta_filenames)
        (dirs, files, is_match) = self.fsal.search(query, whole_words=True)
        for fs_obj in files:
            # since search result paths all point to exact meta files,
            # ``dirname`` is used to return the parent folder
            if relative:
                yield os.path.dirname(fs_obj.rel_path)
            else:
                yield os.path.dirname(fs_obj.path)

    def reload_content(self):
        """Reload all existing content from `contentdir` into database."""
        return sum([self.__add_to_archive(path)
                    for path in self.find_content_dirs()])

    def clear_and_reload(self):
        raise NotImplementedError()

    def last_update(self):
        raise NotImplementedError()

    def add_view(self, relpath):
        raise NotImplementedError()

    def add_tags(self, meta, tags):
        raise NotImplementedError()

    def remove_tags(self, meta, tags):
        raise NotImplementedError()

    def get_tag_name(self, tag_id):
        raise NotImplementedError()

    def get_tag_cloud(self):
        raise NotImplementedError()

    def needs_formatting(self, relpath):
        raise NotImplementedError()

    def get_content_languages(self):
        raise NotImplementedError()
