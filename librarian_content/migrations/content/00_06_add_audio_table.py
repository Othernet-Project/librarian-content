SQL = """
create table audio
(
    path varchar primary key unique not null,
    description varchar
);

create table playlist
(
    path varchar,
    file varchar,
    title varchar,
    duration integer,
    unique(path, file) on conflict replace
);
"""


def up(db, conf):
    db.executescript(SQL)
