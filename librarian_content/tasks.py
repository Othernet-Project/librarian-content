import os

from .library.archive import Archive


def is_content(path, meta_filenames):
    filename = os.path.basename(path)
    return filename in meta_filenames


def check_new_content(supervisor):
    config = supervisor.config
    archive = Archive.setup(config['library.backend'],
                            supervisor.exts.fsal,
                            supervisor.exts.databases.content,
                            contentdir=config['library.contentdir'],
                            meta_filenames=config['library.metadata'])
    for fsobj in supervisor.exts.fsal.get_changes():
        if is_content(fsobj.path, config['library.metadata']):
            archive.add_to_archive(fsobj.path)
        else:
            supervisor.exts.events.publish('FILE_ADDED', fsobj)
