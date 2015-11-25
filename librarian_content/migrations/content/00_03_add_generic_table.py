SQL = """
create table generic
(
    path varchar primary key,
    description varchar
);
"""


def up(db, conf):
    db.executescript(SQL)
