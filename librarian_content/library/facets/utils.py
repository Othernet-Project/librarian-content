from __future__ import unicode_literals

import copy
import logging

from bottle import request

from librarian_core.exts import ext_container as exts
from ...tasks import update_facets_for_dir
from .facets import Facets
from .archive import FacetsArchive, update_facets
from .processors import get_facet_processors


BASE_FACETS = {
    'generic': {
        'path': ''
    }
}


def get_facets(path, partial=True):
    supervisor = request.app.supervisor
    fsal = exts.fsal
    archive = FacetsArchive(fsal, exts.databases.facets,
                            config=supervisor.config)
    facets = archive.get_facets(path)
    if not facets:
        logging.debug("Facets not found for '{}'. Scheduling generation".format(
            path))
        schedule_facets_generation(path, archive)
        if partial:
            facets = generate_partial_facets(path, supervisor, fsal)
    return facets


def generate_partial_facets(path, supervisor, fsal):
    success, dirs, files = fsal.list_dir(path)
    if not success:
        return None
    facets = copy.deepcopy(BASE_FACETS)
    for f in files:
        for processor in get_facet_processors(fsal, path, f.name):
            processor.add_file(facets, f.name, partial=True)
    fill_path(facets, path)
    update_facets(facets)
    return Facets(supervisor, path, facets)


def fill_path(data, path):
    if not isinstance(data, dict):
        return
    data['path'] = path
    for key, value in data.iteritems():
        if isinstance(value, dict):
            fill_path(value, path)
        elif isinstance(value, list):
            for row in value:
                fill_path(row, path)


def schedule_facets_generation(path, archive):
    exts.tasks.schedule(update_facets_for_dir,
                        kwargs=dict(archive=archive,
                                    path=path))
