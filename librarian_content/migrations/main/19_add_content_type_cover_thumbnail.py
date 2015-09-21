SQL = """
alter table zipballs add column content_type int not null default 2;
alter table zipballs add column cover varchar;
alter table zipballs add column thumbnail varchar;
"""


def up(db, conf):
    db.executescript(SQL)
