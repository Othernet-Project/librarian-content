SQL = """
create table image
(
    path varchar primary key
);

create table gallery
(
    path varchar,
    file varchar,
    title varchar,
    width int,
    height int,
    unique(path, file)
);
"""


def up(db, conf):
    db.executescript(SQL)
