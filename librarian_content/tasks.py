import logging
import os

from .library.archive import Archive


def is_content(event, meta_filenames):
    if not event.is_dir and event.event_type == 'created':
        filename = os.path.basename(event.src)
        return filename in meta_filenames
    return False


def check_new_content(supervisor):
    config = supervisor.config
    archive = Archive.setup(config['library.backend'],
                            supervisor.exts.fsal,
                            supervisor.exts.databases.content,
                            contentdir=config['library.contentdir'],
                            meta_filenames=config['library.metadata'])
    for event in supervisor.exts.fsal.get_changes():
        if is_content(event, config['library.metadata']):
            content_path = os.path.dirname(event.src)
            logging.info("New content has been discovered at: '{0}'. Adding it"
                         " to the library...".format(content_path))
            archive.add_to_archive(content_path)
        else:
            supervisor.exts.events.publish('FS_EVENT', event)
