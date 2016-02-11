"""
archive.py: Facets archive

Copyright 2014-2015, Outernet Inc.
Some rights reserved.

This software is free software licensed under the terms of GPLv3. See COPYING
file that comes with the source code, or http://www.gnu.org/licenses/gpl.txt.
"""

import os
import copy
import logging
import functools

from .facets import Facets, FACET_TYPES
from .processors import get_facet_processors


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


class FacetsArchive(object):
    schema = {
        'facets': {
            'constraints': ['path']
        },
        'generic': {
            'constraints': ['path']
        },
        'html': {
            'constraints': ['path', 'index']
        },
        'video': {
            'relations': {'many': ['clips']},
            'constraints': ['path']
        },
        'audio': {
            'relations': {'many': ['playlist']},
            'constraints': ['path']
        },
        'image': {
            'relations': {'many': ['gallery']},
            'constraints': ['path']
        },
        'playlist': {
            'constraints': ['path', 'file'],
            'order': ['file']
        },
        'gallery': {
            'constraints': ['path', 'file'],
            'order': ['file']
        },
        'clips': {
            'constraints': ['path', 'file'],
            'order': ['file']
        },
    }

    def __init__(self, fsal, db, config):
        self.fsal = fsal
        self.db = db
        self.config = config

    @to_dict
    def one(self, *args, **kwargs):
        return self.db.fetchone(*args, **kwargs)

    @to_dict_list
    def many(self, *args, **kwargs):
        return self.db.fetchall(*args, **kwargs)

    def add_to_facets(self, path):
        root = os.path.dirname(path)
        relpath = os.path.relpath(path, root)
        current_facets = self.get_facets(root)
        new_facets = copy.deepcopy(current_facets)
        for processor in get_facet_processors(self.fsal, root, relpath):
            processor.add_file(new_facets, relpath)
        self.save_facets(current_facets, new_facets)

    def remove_from_facets(self, path):
        root = os.path.dirname(path)
        relpath = os.path.relpath(path, root)
        current_facets = self.get_facets(root)
        new_facets = copy.deepcopy(current_facets)
        for processor in get_facet_processors(self.fsal, root, relpath):
            processor.remove_file(new_facets, relpath)
        self.save_facets(current_facets, new_facets)

    def get_facets(self, path):
        q = self.db.Select(sets='facets', where='path = %s')
        data = self.one(q, (path,))
        if data:
            for facet_type, mask in FACET_TYPES.items():
                if data['facet_types'] & mask == mask:
                    self._fetch(facet_type, path, data)
        else:
            data = {'path': path}
        return Facets(supervisor=None, path=None, data=data)

    def save_facets(self, old_facets, new_facets):
        facet_types = 0
        for k, v in FACET_TYPES.items():
            if k in new_facets:
                facet_types |= v
        new_facets['facet_types'] = facet_types

        with self.db.transaction():
            self._write('facets', old_facets, new_facets, shared_data={'path': new_facets['path']})
        return True

    def _fetch(self, table, relpath, dest, many=False):
        q = self.db.Select(sets=table, where='path = %s')
        if 'order' in self.schema[table]:
            q.order = self.schema[table]['order']
        fetcher = self.one if not many else self.many
        dest[table] = fetcher(q, (relpath,))
        relations = self.schema[table].get('relations', {})
        for relation, related_tables in relations.items():
            for rel_table in related_tables:
                self._fetch(rel_table,
                            relpath,
                            dest[table],
                            many=relation == 'many')

    def _write(self, table_name, old_data, new_data, shared_data=None):
        if new_data:
            new_data.update(shared_data)
            new_primitives = {}
            old_primitives = {}
            for key, value in new_data.items():
                old_value = old_data.get(key, None) if old_data else None
                if isinstance(value, dict):
                    self._write(key, old_value, value, shared_data=shared_data)
                elif isinstance(value, list):
                    #TODO: Optimize to find difference between old list and new
                    if old_value:
                        for row in old_value:
                            self._write(key, row, None, shared_data=shared_data)
                    for row in value:
                        self._write(key, None, row, shared_data=shared_data)
                else:
                    new_primitives[key] = value
                    if old_data:
                        old_primitives[key] = old_value

            if old_data:
                # Delete all entries which should no longer exist
                old_keys = set(old_data.keys())
                new_keys = set(new_data.keys())
                removed_keys = old_keys - (old_keys.intersection(new_keys))
                for key in removed_keys:
                    value = old_data[key]
                    self._write(key, value, None, shared_data=shared_data)

            if old_primitives != new_primitives:
                constraints = self.schema[table_name]['constraints']
                q = self.db.Replace(table_name,
                                    constraints=constraints,
                                    cols=new_primitives.keys())
                self.db.execute(q, new_primitives)
        else:
            primitives = {}
            for key, value in old_data.items():
                if isinstance(value, dict):
                    self._write(key, value, None, shared_data=shared_data)
                elif isinstance(value, list):
                    for row in value:
                        self._write(key, row, None, shared_data=shared_data)
                else:
                    primitives[key] = value
            q = self.db.Delete(table_name)
            for key in primitives.keys():
                q.where |= '{0} = %({0})s'.format(key)
            self.db.execute(q, primitives)
