from fsal.client import FSAL

from .commands import refill_facets
from .tasks import check_new_content


def initialize(supervisor):
    supervisor.exts.fsal = FSAL(supervisor.config['fsal.socket'])
    supervisor.exts.commands.register(
        'refill_facets',
        refill_facets,
        '--refill-facets',
        action='store_true',
        help="Empty facets archive and reconstruct it."
    )


def post_start(supervisor):
    refresh_rate = supervisor.config['facets.refresh_rate']
    supervisor.exts.tasks.schedule(check_new_content,
                                   args=(supervisor, refresh_rate),
                                   delay=refresh_rate)
