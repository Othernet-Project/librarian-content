SQL = """
create table html
(
    path varchar primary key unique not null,
    keep_formatting boolean not null default 0,
    main varchar not null default 'index.html'
);
"""


def up(db, conf):
    db.executescript(SQL)
