
G0 = 0
G1_MAIN_DEFAULT = 'index.html'
G1_KEEP_FORMATTING_DEFAULT = False


def has_clues(meta):
    clues = ('index', 'keep_formatting', 'images', 'multipage')
    return any([key in meta for key in clues])


def get_generation(meta):
    return G0 if has_clues(meta) else None


def upgrade_to_next(meta):
    for ignored in ('images', 'multipage'):
        meta.pop(ignored, None)

    main = meta.pop('index', G1_MAIN_DEFAULT)
    keep_formatting = meta.pop('keep_formatting', G1_KEEP_FORMATTING_DEFAULT)
    meta['gen'] = G0 + 1
    meta['content'] = {
        'html': {
            'main': main,
            'keep_formatting': keep_formatting
        }
    }
