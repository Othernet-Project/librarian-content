import functools

from librarian_core.utils import is_string


def to_list(func):
    """In case a single string parameter is passed to the function wrapped
    with this decorator, the single parameter will be wrapped in a list."""
    @functools.wraps(func)
    def wrapper(self, arg):
        if is_string(arg):
            arg = [arg]
        return func(self, arg)
    return wrapper
