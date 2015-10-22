SQL = """
create table content
(
    path varchar primary_key unique not null,
    url varchar not null,
    title varchar not null,
    timestamp timestamp not null,
    updated timestamp not null,
    favorite boolean not null default 0,
    views integer not null default 0,
    is_partner boolean not null default 0,
    is_sponsored boolean not null default 0,
    archive varchar not null default 'core',
    publisher varchar,
    license varchar,
    tags varchar,
    language varchar,
    size integer,
    broadcast date,
    keywords varchar not null default '',
    disabled boolean not null default 0,
    content_type int not null default 1,  --default content type is ``generic``
    cover varchar,
    thumbnail varchar
);
"""


def up(db, conf):
    db.executescript(SQL)
