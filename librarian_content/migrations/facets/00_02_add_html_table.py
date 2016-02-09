SQL = """
create table html
(
    path varchar primary key,
    index varchar not null
);
"""


def up(db, conf):
    db.executescript(SQL)
