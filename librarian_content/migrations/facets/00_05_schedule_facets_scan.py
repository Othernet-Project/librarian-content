from librarian_core.exts import ext_container as exts

from ...tasks import scan_facets


SCAN_DELAY = 5
STEP_DELAY = 0.5


def up(db, conf):
    start_delay = conf.get('facets.scan_delay', SCAN_DELAY)
    step_delay = conf.get('facets.scan_step_delay', STEP_DELAY)
    exts.tasks.schedule(scan_facets,
                        kwargs=dict(step_delay=step_delay, config=conf),
                        delay=start_delay)
