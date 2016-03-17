SQL = """
create table video
(
    path varchar primary key unique not null
);

create table clips
(
    path varchar,
    file varchar,
    title varchar,
    author varchar,
    description varchar,
    duration integer,
    width integer,
    height integer,
    thumbnail varchar,
    unique(path, file) on conflict replace
);
"""


def up(db, conf):
    db.executescript(SQL)
