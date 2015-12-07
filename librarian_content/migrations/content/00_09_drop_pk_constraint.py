SQL = """
ALTER TABLE album DROP CONSTRAINT album_pkey;
ALTER TABLE album DROP CONSTRAINT album_path_file_key;
ALTER TABLE playlist DROP CONSTRAINT playlist_pkey;
ALTER TABLE playlist DROP CONSTRAINT playlist_path_file_key;

ALTER TABLE album ADD PRIMARY KEY (path, file);
ALTER TABLE playlist ADD PRIMARY KEY (path, file);
"""


def up(db, conf):
    db.executescript(SQL)
