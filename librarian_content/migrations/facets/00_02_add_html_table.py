SQL = """
create table html
(
    path varchar primary key unique not null,
    index varchar not null,

    unique(path, index)
);
"""


def up(db, conf):
    db.executescript(SQL)
