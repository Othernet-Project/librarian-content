import logging
import datetime
import functools
import itertools

from bottle_utils.common import to_unicode
from hachoir_parser import createParser
from hachoir_metadata import extractMetadata


def meta_tags(tags, default=None, transform=None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self):
            items = (self._meta.getItem(tag, 0) for tag in tags)
            values = (item.value for item in items if item)
            transformed = itertools.imap(transform, values)
            value = next(transformed, default)
            return value
        return wrapper
    return decorator


def to_seconds(duration):
    if isinstance(duration, datetime.timedelta):
        duration = int(duration.total_seconds())
    return duration


class BaseMetadata(object):

    def __init__(self, fsal, path):
        self.fsal = fsal
        self.path = path

    def get(self, key, default=None):
        raise NotImplementedError()


class HachoirMetadataWrapper(BaseMetadata):

    def __init__(self, *args, **kwargs):
        super(HachoirMetadataWrapper, self).__init__(*args, **kwargs)

        success, fso = self.fsal.get_fso(self.path)
        if not success:
            msg = 'Error while extracting metadata. No such file: {}'.format(fso.path)
            logging.error(msg)
            raise IOError(msg)
        try:
            parser = createParser(to_unicode(fso.path))
            metadata = extractMetadata(parser)
            self._meta = metadata
        except IOError as e:
            logging.error("Error while extracting metadata from '{}': {}".format(fso.path, str(e)))
            raise

    def get(self, key, default=None):
        return self._meta.get(key, default)


class ImageMetadata(HachoirMetadataWrapper):

    @property
    @meta_tags(tags=('title',), default='')
    def title(self):
        pass

    @property
    @meta_tags(tags=('width',), default=0)
    def width(self):
        pass

    @property
    @meta_tags(tags=('height',), default=0)
    def height(self):
        pass


class AudioMetadata(HachoirMetadataWrapper):

    @property
    @meta_tags(tags=('artist', 'author'), default='')
    def artist(self):
        pass

    @property
    @meta_tags(tags=('title',), default='')
    def title(self):
        pass

    @property
    @meta_tags(tags=('duration',), default=0, transform=to_seconds)
    def duration(self):
        pass


class VideoMetadata(HachoirMetadataWrapper):

    @property
    @meta_tags(tags=('title',), default='')
    def title(self):
        pass

    @property
    @meta_tags(tags=('width',), default=0)
    def width(self):
        pass

    @property
    @meta_tags(tags=('height',), default=0)
    def height(self):
        pass

    @property
    @meta_tags(tags=('duration',), default=0, transform=to_seconds)
    def duration(self):
        pass
