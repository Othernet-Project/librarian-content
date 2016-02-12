import functools

from bottle import abort, request
from bottle_utils.html import urlunquote

from librarian_content.library import metadata
from librarian_content.library.archive import Archive
from librarian_content.library.facets.facets import Facets
from librarian_content.library.facets.archive import FacetsArchive


def with_meta(abort_if_not_found=True):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(path, **kwargs):
            path = urlunquote(path)
            conf = request.app.config
            archive = Archive.setup(conf['library.backend'],
                                    request.app.supervisor.exts.fsal,
                                    request.db.content,
                                    meta_filenames=conf['library.metadata'])
            content = archive.get_single(path)
            if not content:
                if abort_if_not_found:
                    abort(404)
                return func(path=path, meta=None, **kwargs)

            meta = metadata.Meta(request.app.supervisor,
                                 content.path,
                                 data=content)
            return func(path=path, meta=meta, **kwargs)
        return wrapper
    return decorator


def with_facets(abort_if_not_found=True):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(path, **kwargs):
            path = urlunquote(path)
            conf = request.app.config
            archive = FacetsArchive(request.app.supervisor.exts.fsal,
                                    request.db.facets,
                                    config=conf)
            data = archive.get_facets(path)
            if not data:
                if abort_if_not_found:
                    abort(404)
                return func(path=path, facets=None, **kwargs)

            facets = Facets(request.app.supervisor, data.path, data=data)
            return func(path=path, facets=facets, **kwargs)
        return wrapper
    return decorator
