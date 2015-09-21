import os

# TODO: import real fsal library
import mock
fsal = mock.Mock()

from .helpers import open_archive


def is_content(path, meta_filename='.contentinfo'):
    filename = os.path.basename(path)
    return filename == meta_filename


def check_new_content(supervisor):
    config = supervisor.config
    archive = open_archive(config=config)
    for path in fsal.get_changes():
        if is_content(path, meta_filename=config['library.metadata']):
            archive.add_to_archive(path)
