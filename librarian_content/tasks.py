import functools
import logging
import os

from fsal.events import EVENT_CREATED, EVENT_DELETED, EVENT_MODIFIED

from librarian_core.exts import ext_container as exts

from .library.archive import Archive
from .library.facets.archive import FacetsArchive


REPEAT_DELAY = 3  # seconds
INCREMENT_DELAY = 5  # surprisignly also seconds


def is_content(event, meta_filenames):
    if not event.is_dir:
        filename = os.path.basename(event.src)
        return filename in meta_filenames
    return False


def reschedule_content_check(fn):
    @functools.wraps(fn)
    def wrapper(supervisor, current_delay):
        try:
            changes_found = fn(supervisor)
        except Exception:
            changes_found = False
            raise
        finally:
            if changes_found:
                refresh_rate = REPEAT_DELAY
            else:
                max_delay = supervisor.config['library.refresh_rate']
                if current_delay + INCREMENT_DELAY <= max_delay:
                    refresh_rate = current_delay + INCREMENT_DELAY
                else:
                    refresh_rate = max_delay

            supervisor.exts.tasks.schedule(check_new_content,
                                           args=(supervisor, refresh_rate),
                                           delay=refresh_rate)
    return wrapper


@reschedule_content_check
def check_new_content(supervisor):
    config = supervisor.config
    archive = Archive.setup(config['library.backend'],
                            supervisor.exts.fsal,
                            supervisor.exts.databases.content,
                            meta_filenames=config['library.metadata'])
    facets_archive = FacetsArchive(supervisor.exts.fsal,
                                   supervisor.exts.databases.facets,
                                   config=config)
    changes_found = False
    for event in supervisor.exts.fsal.get_changes():
        changes_found = True
        fpath = event.src
        is_file = not event.is_dir
        if is_file and event.event_type in (EVENT_CREATED, EVENT_MODIFIED):
            logging.info(u"Adding file to facets archive: '{}'".format(fpath))
            facets_archive.update_facets(fpath)
        elif is_file and event.event_type == EVENT_DELETED:
            logging.info(u"Removing file from facets archive: '{}'".format(
                fpath))
            facets_archive.remove_facets(fpath)

        path = os.path.dirname(event.src)
        if is_content(event, config['library.metadata']):
            if event.event_type == 'created':
                logging.info(u"New content has been discovered at: '{}'."
                             " Adding it to the library...".format(path))
                archive.add_to_archive(path)
            elif event.event_type == 'deleted':
                logging.info(u"Content removed from filesystem: '{}'."
                             " Removing it from the library...".format(path))
                archive.remove_from_archive(path, delete_files=False)

        supervisor.exts.events.publish('FS_EVENT', event)

    if changes_found:
        supervisor.exts.cache.invalidate('content')

    return changes_found


def generate_facets(paths, archive):
    for path in paths:
        logging.debug(u'Scheduled facet generation triggered for {}'.format(
            path))
        success, fso = exts.fsal.get_fso(path)
        if not success:
            logging.debug(u'Facet gen cancelled. {} does not exist'.format(
                path))
            continue
        facets = archive.get_facets(path)
        if facets:
            logging.debug(u'Facets already generated for {}'.format(
                path))
            continue
        logging.debug(u"Generating facets for '{}'".format(path))
        archive.update_facets(path)
