SQL = """
create table audio
(
    path varchar primary key,
    cover varchar
);

create table playlist
(
    path varchar primary key,
    file varchar,
    artist varchar,
    title varchar,
    duration integer,
    unique(path, file)
);
"""


def up(db, conf):
    db.executescript(SQL)
