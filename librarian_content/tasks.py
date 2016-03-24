import functools
import logging
import os
import collections

from fsal.events import EVENT_CREATED, EVENT_DELETED, EVENT_MODIFIED

from librarian_core.exts import ext_container as exts

from .library.archive import Archive
from .library.facets.utils import get_archive


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
    facets_archive = get_archive(db=supervisor.exts.databases.facets,
                                 config=config)
    changes_found = False
    for event in supervisor.exts.fsal.get_changes():
        changes_found = True
        fpath = event.src
        is_file = not event.is_dir
        if is_file and event.event_type in (EVENT_CREATED, EVENT_MODIFIED):
            logging.info(u"Update files facets: '{}'".format(fpath))
            facets_archive.update_facets(fpath)
        elif is_file and event.event_type == EVENT_DELETED:
            logging.info(u"Removing file facets: '{}'".format(fpath))
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


def scan_facets(path_queue=None, step_delay=0, config=None):
    if path_queue is None:
        path_queue = collections.deque()
        path_queue.append('.')
    if not path_queue:
        logging.info(u'Facets scan complete.')
        return

    dir_path = path_queue.popleft()
    logging.debug(u'Scanning facets for files in {}'.format(dir_path))
    success, dirs, files = exts.fsal.list_dir(dir_path)
    if not success:
        logging.warn(
            u'Facets scan for {} stopped. Invalid path.'.format(dir_path))
        return

    archive = get_archive(config=config)
    for f in files:
        logging.info(u"Update file facets: '{}'".format(f.rel_path))
        archive.update_facets(f.rel_path)
    for d in dirs:
        path_queue.append(d.rel_path)
    kwargs = dict(path_queue=path_queue, step_delay=step_delay,
                  config=config)
    exts.tasks.schedule(scan_facets, kwargs=kwargs)
