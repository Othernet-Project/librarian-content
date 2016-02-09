SQL = """
create table generic
(
    path varchar primary key
);
"""


def up(db, conf):
    db.executescript(SQL)
