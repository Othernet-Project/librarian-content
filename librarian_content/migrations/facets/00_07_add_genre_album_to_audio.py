SQL = """
alter table playlist
    add column genre varchar,
    add column album varchar;
"""


def up(db, conf):
    db.executescript(SQL)
