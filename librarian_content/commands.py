from .library.archive import Archive


def refill_db(arg, supervisor):
    print('Begin content refill.')
    config = supervisor.config
    archive = Archive.setup(config['library.backend'],
                            supervisor.exts.fsal,
                            supervisor.exts.databases.content,
                            contentdir=config['library.contentdir'],
                            meta_filenames=config['library.metadata'])
    archive.clear_and_reload()
    print('Content refill finished.')
    raise supervisor.EarlyExit()


def reload_db(arg, supervisor):
    print('Begin content reload.')
    config = supervisor.config
    archive = Archive.setup(config['library.backend'],
                            supervisor.exts.fsal,
                            supervisor.exts.databases.content,
                            contentdir=config['library.contentdir'],
                            meta_filenames=config['library.metadata'])
    archive.reload_content()
    print('Content reload finished.')
    raise supervisor.EarlyExit()
