import os


def up(db, conf):
    # delete old main database
    for ext in ('sqlite', 'sqlite-shm', 'sqlite-wal'):
        filename = os.path.join(conf['database.path'], 'main.{0}'.format(ext))
        if os.path.exists(filename):
            os.remove(filename)
