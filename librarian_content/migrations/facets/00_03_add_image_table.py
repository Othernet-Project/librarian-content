SQL = """
create table image
(
    path varchar primary key unique not null
);

create table gallery
(
    path varchar,
    file varchar,
    title varchar,
    width int,
    height int,
    unique(path, file) on conflict replace
);
"""


def up(db, conf):
    db.executescript(SQL)
