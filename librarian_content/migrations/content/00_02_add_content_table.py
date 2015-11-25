SQL = """
create table content
(
    path varchar primary key,
    url varchar not null,
    title varchar not null,
    timestamp timestamptz not null,
    updated timestamptz not null,
    favorite boolean not null default false,
    views integer not null default 0,
    is_partner boolean not null default false,
    is_sponsored boolean not null default false,
    archive varchar not null default 'core',
    publisher varchar,
    license varchar,
    tags varchar,
    language varchar,
    size integer,
    broadcast date,
    keywords varchar not null default '',
    disabled boolean not null default false,
    content_type int not null default 1,  --default content type is ``generic``
    cover varchar,
    thumbnail varchar
);
"""


def up(db, conf):
    db.executescript(SQL)
