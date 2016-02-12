from fsal.client import FSAL

from .commands import refill_db, reload_db, refill_facets
from .tasks import check_new_content
from .utils import ensure_dir


def initialize(supervisor):
    supervisor.exts.fsal = FSAL(supervisor.config['fsal.socket'])
    supervisor.exts.commands.register(
        'refill',
        refill_db,
        '--refill',
        action='store_true',
        help="Empty database and then reload zipballs into it."
    )
    supervisor.exts.commands.register(
        'reload',
        reload_db,
        '--reload',
        action='store_true',
        help="Reload zipballs into database without clearing it previously."
    )
    supervisor.exts.commands.register(
        'refill_facets',
        refill_facets,
        '--refill-facets',
        action='store_true',
        help="Empty facets archive and reconstruct it."
    )


def post_start(supervisor):
    refresh_rate = supervisor.config['library.refresh_rate']
    supervisor.exts.tasks.schedule(check_new_content,
                                   args=(supervisor, refresh_rate),
                                   delay=refresh_rate)
