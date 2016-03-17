SQL = """
create table generic
(
    path varchar primary key unique not null
);
"""


def up(db, conf):
    db.executescript(SQL)
