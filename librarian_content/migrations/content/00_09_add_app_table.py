SQL = """
create table app
(
    path varchar primary key,
    version varchar,
    description varchar
);
"""


def up(db, conf):
    db.executescript(SQL)
