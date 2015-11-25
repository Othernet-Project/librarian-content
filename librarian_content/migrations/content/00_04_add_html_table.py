SQL = """
create table html
(
    path varchar primary key,
    keep_formatting boolean not null default false,
    main varchar not null default 'index.html'
);
"""


def up(db, conf):
    db.executescript(SQL)
