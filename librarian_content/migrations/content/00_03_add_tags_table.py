SQL = """
create table tags
(
    tag_id serial primary key,
    name varchar not null unique
);
create table taggings
(
    tag_id integer,
    path varchar,
    unique (tag_id, path)
);
"""


def up(db, conf):
    db.executescript(SQL)
