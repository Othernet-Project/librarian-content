SQL = """
create table video
(
    path varchar primary key,
    main varchar not null default 'video.mp4',
    duration integer,
    resolution varchar,
    description varchar
);
"""


def up(db, conf):
    db.executescript(SQL)
