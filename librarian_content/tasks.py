import os

# TODO: import real fsal library
import mock
fsal = mock.Mock()

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
    for path in fsal.get_changes():
        if is_content(path, meta_filename=config['library.metadata']):
            archive.add_to_archive(path)
