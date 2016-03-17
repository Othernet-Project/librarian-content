SQL = """
create table image
(
    path varchar primary key unique not null,
    description varchar
);

create table album
(
    path varchar,
    file varchar,
    thumbnail varchar,
    caption varchar,
    title varchar,
    resolution varchar,
    unique(path, file) on conflict replace
);
"""


def up(db, conf):
    db.executescript(SQL)
