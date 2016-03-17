SQL = """
create table generic
(
    path varchar primary key unique not null,
    description varchar
);
"""


def up(db, conf):
    db.executescript(SQL)
