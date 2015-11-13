import logging
import os

from .library.archive import Archive


REPEAT_DELAY = 3  # seconds


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
    changes_found = False
    for event in supervisor.exts.fsal.get_changes():
        changes_found = True
        path = os.path.dirname(event.src)
        if is_content(event, config['library.metadata']):
            logging.info(u"New content has been discovered at: '{0}'. Adding "
                         "it to the library...".format(path))
            archive.add_to_archive(path)
        else:
            supervisor.exts.events.publish('FS_EVENT', event)

    if changes_found:
        supervisor.exts.cache.invalidate('content')
        refresh_rate = REPEAT_DELAY
    else:
        refresh_rate = config['library.refresh_rate']

    supervisor.exts.tasks.schedule(check_new_content,
                                   args=(supervisor,),
                                   delay=refresh_rate)
