SQL = """
create table html
(
    path varchar primary key,
    index varchar not null,

    unique(path, index)
);
"""


def up(db, conf):
    db.executescript(SQL)
