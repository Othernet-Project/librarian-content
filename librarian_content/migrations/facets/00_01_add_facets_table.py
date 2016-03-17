SQL = """
create table facets
(
    path varchar primary key unique not null,
    facet_types int not null default 1  --default type is general
);
"""


def up(db, conf):
    db.executescript(SQL)
