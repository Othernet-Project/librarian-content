SQL = """
drop table facets;
drop table html;
drop table image;
drop table gallery;
drop table generic;
drop table audio;
drop table playlist;
drop table video;
drop table clips;
"""


def up(db, conf):
    db.executescript(SQL)
