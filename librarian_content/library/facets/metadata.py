import logging
import datetime

from bottle_utils.common import to_unicode
from hachoir_parser import createParser
from hachoir_metadata import extractMetadata


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
        value = self._meta.get(key, default)
        if key == 'duration' and isinstance(value, datetime.timedelta):
            value = int(value.total_seconds())
        return value


class ImageMetadata(HachoirMetadataWrapper):
    pass


class AudioMetadata(HachoirMetadataWrapper):
    pass


class VideoMetadata(HachoirMetadataWrapper):
    pass
