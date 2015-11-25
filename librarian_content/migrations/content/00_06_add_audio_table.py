SQL = """
create table audio
(
    path varchar primary key,
    description varchar
);

create table playlist
(
    path varchar primary key,
    file varchar,
    title varchar,
    duration integer,
    unique(path, file)
);
"""


def up(db, conf):
    db.executescript(SQL)
