
G0 = 0


def has_clues(meta):
    clues = ('index', 'keep_formatting', 'images', 'multipage')
    return any([key in meta for key in clues])


def get_generation(meta):
    return G0 if has_clues(meta) else None


def upgrade_to_next(meta):
    for ignored in ('index', 'keep_formatting', 'images', 'multipage'):
        meta.pop(ignored, None)

    meta['gen'] = G0 + 1
    meta['content'] = {
        'generic': {}
    }
