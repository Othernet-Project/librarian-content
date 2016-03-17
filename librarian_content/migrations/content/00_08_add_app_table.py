SQL = """
create table app
(
    path varchar primary key unique not null,
    version varchar,
    description varchar
);
"""


def up(db, conf):
    db.executescript(SQL)
