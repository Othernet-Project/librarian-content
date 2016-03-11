import copy

from bottle import request

from librarian_core.exts import ext_container as exts
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
    if not facets and partial:
        facets = generate_partial_facets(path, supervisor, fsal)
        # TODO: Schedule a facet generation with metadata extraction
    return facets


def generate_partial_facets(path, supervisor, fsal):
    success, dirs, files = fsal.list_dir(path)
    if not success:
        return None
    facets = copy.deepcopy(BASE_FACETS)
    for f in files:
        for processor in get_facet_processors(fsal, path, f.name):
            processor.add_file(facets, f.name, partial=True)
    stuff_path(facets, path)
    update_facets(facets)
    return Facets(supervisor, path, facets)


def stuff_path(facets, path):
    if not isinstance(facets, dict):
        return
    facets['path'] = path
    for key, value in facets.iteritems():
        if isinstance(value, dict):
            stuff_path(value, path)
        elif isinstance(value, list):
            for row in value:
                stuff_path(row, path)
