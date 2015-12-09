SQL = """
ALTER TABLE content DROP COLUMN url;
ALTER TABLE content DROP COLUMN archive;
"""


def up(db, conf):
    db.executescript(SQL)
