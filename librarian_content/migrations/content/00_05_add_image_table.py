SQL = """
create table image
(
    path varchar primary key,
    description varchar
);

create table album
(
    path varchar primary key,
    file varchar,
    thumbnail varchar,
    caption varchar,
    title varchar,
    resolution varchar,
    unique(path, file)
);
"""


def up(db, conf):
    db.executescript(SQL)
