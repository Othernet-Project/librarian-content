SQL = """
create table tags
(
    tag_id integer primary key asc,
    name varchar not null unique on conflict ignore
);
create table taggings
(
    tag_id integer,
    path varchar,
    unique (tag_id, path) on conflict ignore
);
"""


def up(db, conf):
    db.executescript(SQL)
