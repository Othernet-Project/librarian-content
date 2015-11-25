"""
archive.py: Download handling

Copyright 2014-2015, Outernet Inc.
Some rights reserved.

This software is free software licensed under the terms of GPLv3. See COPYING
file that comes with the source code, or http://www.gnu.org/licenses/gpl.txt.
"""

import functools
import logging

from ...archive import BaseArchive, metadata


CONTENT_ORDER = ['-date(updated)', '-views']


def multiarg(query, n):
    """ Returns version of query where '??' is replaced by n placeholders """
    return query.replace('??', ', '.join(['%s'] * n))


class AttrDict(dict):

    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


def row_to_dict(row):
    return AttrDict((key, row[key]) for key in row.keys())


def to_dict(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        row = func(*args, **kwargs)
        if not row:
            return row
        return row_to_dict(row)
    return wrapper


def to_dict_list(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        rows = func(*args, **kwargs)
        if not rows:
            return rows
        return map(row_to_dict, rows)
    return wrapper


class Transformation(object):
    pass


class Merge(Transformation):
    """Merge into parent"""
    pass


class Ignore(Transformation):
    """Ignores / deletes key and value"""
    pass


class Rename(Transformation):
    """Renames key to specified name"""
    def __init__(self, name):
        self.name = name


class EmbeddedArchive(BaseArchive):
    transformations = [
        {'content': Merge},
        {'replaces': Ignore},
        {'video': [
            {'size': Rename('resolution')}
        ]},
        {'image': [
            {'size': Rename('resolution')}
        ]}
    ]
    content_schema = {
        'generic': {},
        'html': {},
        'video': {},
        'audio': {'many': ['playlist']},
        'app': {},
        'image': {'many': ['album']},
        'playlist': {},
        'album': {}
    }

    @to_dict
    def one(self, *args, **kwargs):
        return self.db.fetchone(*args, **kwargs)

    @to_dict_list
    def many(self, *args, **kwargs):
        return self.db.fetchall(*args, **kwargs)

    def __init__(self, fsal, db, **config):
        self.db = db
        super(EmbeddedArchive, self).__init__(fsal, **config)

    def _serialize(self, metadata, transformations):
        for transformer in transformations:
            ((key, action),) = transformer.items()
            if isinstance(action, list) and key in metadata:
                self._serialize(metadata[key], action)
            elif action is Merge:
                value = metadata.pop(key, None)
                if value is not None:
                    metadata.update(value)
            elif action is Ignore:
                metadata.pop(key, None)
            elif isinstance(action, Rename):
                value = metadata.pop(key, None)
                if value is not None:
                    metadata[action.name] = value

    def _add_filters(self, q, terms, lang, content_type):
        if lang:
            q.where += 'language = %(lang)s'

        if terms:
            q.where += ('title LIKE %(terms)s OR '
                        'publisher LIKE %(terms)s OR '
                        'keywords LIKE %(terms)s')

        if content_type:
            # get integer representation of content type
            content_type_id = metadata.CONTENT_TYPES[content_type]
            q.where += '("content_type" & %(content_type)s) = %(content_type)s'
        else:
            # exclude content types that cannot be displayed on the mixed type
            # content list
            content_type_id = sum([metadata.CONTENT_TYPES[name]
                                   for name in self.exclude_from_content_list])
            qs = '("content_type" & %(content_type)s) != %(content_type)s'
            q.where += qs

        return (q, content_type_id)

    def get_count(self, terms=None, lang=None, content_type=None):
        q = self.db.Select('COUNT(*) as count',
                           sets='content',
                           where='disabled = false')
        (q, content_type_id) = self._add_filters(q,
                                                 terms,
                                                 lang,
                                                 content_type)
        terms = '%' + terms.lower() + '%'
        result = self.db.fetchone(q, dict(terms=terms,
                                          lang=lang,
                                          content_type=content_type_id))
        return result['count']

    def get_content(self, terms=None, offset=0, limit=0, lang=None,
                    content_type=None):
        # TODO: tests
        q = self.db.Select(sets='content',
                           where='disabled = false',
                           order=CONTENT_ORDER,
                           limit=limit,
                           offset=offset)
        (q, content_type_id) = self._add_filters(q,
                                                 terms,
                                                 lang,
                                                 content_type)
        terms = '%' + terms.lower() + '%'
        results = self.many(q, dict(terms=terms,
                                    lang=lang,
                                    content_type=content_type_id))
        if results and content_type in self.prefetchable_types:
            for meta in results:
                self._fetch(content_type, meta['path'], meta)

        return results

    def _fetch(self, table, relpath, dest, many=False):
        q = self.db.Select(sets=table, where='path = %s')
        fetcher = self.one if not many else self.many
        dest[table] = fetcher(q, (relpath,))
        for relation, related_tables in self.content_schema[table].items():
            for rel_table in related_tables:
                self._fetch(rel_table,
                            relpath,
                            dest[table],
                            many=relation == 'many')

    def get_single(self, relpath):
        q = self.db.Select(sets='content', where='path = %s')
        data = self.one(q, (relpath,))
        if data:
            for content_type, mask in metadata.CONTENT_TYPES.items():
                if data['content_type'] & mask == mask:
                    self._fetch(content_type, relpath, data)
        return data

    def get_multiple(self, relpaths, fields=None):
        q = self.db.Select(what=['*'] if fields is None else fields,
                           sets='content',
                           where=self.db.sqlin('path', relpaths))
        return self.many(q, relpaths)

    def content_for_domain(self, domain):
        # TODO: tests
        q = self.db.Select(sets='content',
                           where='url LIKE %(domain)s AND disabled = false',
                           order=CONTENT_ORDER)
        domain = '%' + domain.lower() + '%'
        return self.many(q, dict(domain=domain))

    def _write(self, table_name, data, shared_data=None):
        data.update(shared_data)
        primitives = {}
        for key, value in data.items():
            if isinstance(value, dict):
                self._write(key, value, shared_data=shared_data)
            elif isinstance(value, list):
                for row in value:
                    self._write(key, row, shared_data=shared_data)
            else:
                primitives[key] = value

        q = self.db.Replace(table_name,
                            constraints=shared_data.keys(),
                            cols=primitives.keys())
        self.db.execute(q, primitives)

    def add_meta_to_db(self, metadata):
        with self.db.transaction():
            logging.debug("Adding new content to archive database")
            replaces = metadata.get('replaces')
            self._serialize(metadata, self.transformations)
            self._write('content',
                        metadata,
                        shared_data={'path': metadata['path']})
            if replaces:
                msg = "Removing replaced content from archive database."
                logging.debug(msg)
                q = self.db.Delete('content', where='path = %s')
                self.db.execute(q, (replaces,))

        return True

    def remove_meta_from_db(self, relpath):
        with self.db.transaction() as cur:
            msg = "Removing {0} from archive database".format(relpath)
            logging.debug(msg)
            q = self.db.Delete('content', where='path = %s')
            rowcount = self.db.execute(q, (relpath,))
            for table in self.content_schema.keys():
                q = self.db.Delete(table, where='path = %s')
                self.db.execute(q, (relpath,))
            return rowcount

    def clear_and_reload(self):
        logging.debug('Content refill started.')
        q = self.db.Delete('content')
        self.db.execute(q)
        rows = self.reload_content()
        logging.info('Content refill finished for %s pieces of content', rows)

    def last_update(self):
        """ Get timestamp of the last updated content item

        :returns:  datetime object of the last updated content item
        """
        q = self.db.Select('updated',
                           sets='content',
                           order='-updated',
                           limit=1)
        res = self.db.fetchone(q)
        return res and res['updated']

    def add_view(self, relpath):
        """ Increments the viewcount for content with specified relpath

        :param relpath:  Relative path of content item
        :returns:        ``True`` if successful, ``False`` otherwise
        """
        q = self.db.Update('content', views='views + 1', where='path = %s')
        rowcount = self.db.execute(q, (relpath,))
        assert rowcount == 1, 'Updated more than one row'
        return rowcount

    def needs_formatting(self, relpath):
        """ Whether content needs formatting patch """
        q = self.db.Select('keep_formatting',
                           sets='content',
                           where='path = %s')
        result = self.db.fetchone(q, (relpath,))
        return not result['keep_formatting']

    def get_content_languages(self):
        q = 'SELECT DISTINCT language FROM content'
        languages = self.db.fetchiter(q)
        return [row['language'] for row in languages]
