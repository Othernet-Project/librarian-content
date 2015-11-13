from fsal.client import FSAL

from .commands import refill_db, reload_db
from .tasks import check_new_content
from .utils import ensure_dir


def initialize(supervisor):
    ensure_dir(supervisor.config['library.contentdir'])
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


def post_start(supervisor):
    refresh_rate = supervisor.config['library.refresh_rate']
    supervisor.exts.tasks.schedule(check_new_content,
                                   args=(supervisor,),
                                   delay=refresh_rate)
