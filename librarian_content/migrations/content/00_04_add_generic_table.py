SQL = """
create table generic
(
    path varchar primary_key unique not null,
    description varchar
);
"""


def up(db, conf):
    db.executescript(SQL)
