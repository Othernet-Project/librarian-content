import os

import fsal

from .library.archive import Archive


def is_content(path, meta_filename='.contentinfo'):
    filename = os.path.basename(path)
    return filename == meta_filename


def check_new_content(supervisor):
    config = supervisor.config
    archive = Archive.setup(config['library.backend'],
                            supervisor.exts.databases.content,
                            contentdir=config['library.contentdir'],
                            meta_filename=config['library.metadata'])
    for fsobj in fsal.get_changes():
        if is_content(fsobj.path, meta_filename=config['library.metadata']):
            archive.add_to_archive(fsobj.path)
        else:
            supervisor.events.publish('FILE_ADDED', fsobj)
