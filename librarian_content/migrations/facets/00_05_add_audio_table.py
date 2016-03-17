SQL = """
create table audio
(
    path varchar primary key unique not null,
    cover varchar
);

create table playlist
(
    path varchar,
    file varchar,
    author varchar,
    title varchar,
    duration integer,
    genre varchar,
    album varchar,
    unique(path, file) on conflict replace
);
"""


def up(db, conf):
    db.executescript(SQL)
