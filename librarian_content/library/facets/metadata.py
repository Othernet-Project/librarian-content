from __future__ import unicode_literals

import json
import gevent
import logging
import datetime
import functools
import itertools
import subprocess

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


def run_command(command, timeout, debug=False):
    start = datetime.datetime.now()
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    if debug:
        logging.debug('Command ({}) started at pid {}'.format(' '.join(command), process.pid))
    while process.poll() is None:
        gevent.sleep(0.1)
        now = datetime.datetime.now()
        if (now - start).seconds > timeout:
            if debug:
                logging.debug('Command ({}) ran past timeout of {} secs and will be terminated'.format(' '.join(command), timeout))
            process.kill()
            return None
    if debug:
        logging.debug('Command with pid {} ended normally with return code {}'.format(process.pid, process.returncode))
    return process.stdout.read()


class BaseMetadata(object):

    def __init__(self, fsal, path):
        self.fsal = fsal
        self.path = to_unicode(path)

    def get(self, key, default=None):
        raise NotImplementedError()


class HachoirMetadataWrapper(BaseMetadata):

    def __init__(self, *args, **kwargs):
        super(HachoirMetadataWrapper, self).__init__(*args, **kwargs)

        success, fso = self.fsal.get_fso(self.path)
        if not success:
            msg = u'Error while extracting metadata. No such file: {}'.format(self.path)
            logging.error(msg)
            raise IOError(msg)
        try:
            parser = createParser(to_unicode(fso.path))
            metadata = extractMetadata(parser)
            self._meta = metadata
        except IOError as e:
            logging.error(u"Error while extracting metadata from '{}': {}".format(fso.path, str(e)))
            raise

    def get(self, key, default=None):
        return self._meta.get(key, default)


class FFmpegMetadataWrapper(BaseMetadata):

    def __init__(self, *args, **kwargs):
        super(FFmpegMetadataWrapper, self).__init__(*args, **kwargs)

        success, fso = self.fsal.get_fso(self.path)
        if not success:
            msg = u'Error while extracting metadata: No such file: {}'.format(self.path)
            logging.error(msg)
            raise IOError(msg)
        command = self.build_command(fso.path)
        output = run_command(command, timeout=5, debug=True)
        if not output:
            msg = u'Error while extracting metadata: Metadata extraction timedout or failed'
            raise IOError(msg)
        try:
            self.data = json.loads(output)
        except ValueError:
            msg = u'Error while extracting metadata: Metadata extraction timedout or failed'
            raise IOError(msg)

    @staticmethod
    def build_command(path):
        COMMAND_TEMPLATE = 'ffprobe -v quiet -i PLACEHOLDER -show_entries format:streams -print_format json'
        command = COMMAND_TEMPLATE.split(' ')
        command[4] = path
        return command

    def get_dimensions(self):
        streams = self.data.get('streams', list())
        for stream in streams:
            if 'width' in stream:
                width = stream['width']
                height = stream['height']
                return width, height
        return 0, 0

    def get_duration(self):
        fmt = self.data.get('format', dict())
        if 'duration' in fmt:
            return float(fmt['duration'])
        streams = self.data.get('streams', list())
        duration = 0
        for stream in streams:
            if 'duration' in stream:
                s_duration = float(stream['duration'])
                if duration < s_duration:
                    duration = s_duration
        return duration

    def get_fmt_tags(self, tags, default=''):
        fmt = self.data.get('format', dict())
        fmt_tags = fmt.get('tags', dict())
        for tag in tags:
            if tag in fmt_tags:
                return fmt_tags[tag]
        return default


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


class FFmpegAudioVideoMetadata(FFmpegMetadataWrapper):
    def __init__(self, *args, **kwargs):
        super(FFmpegAudioVideoMetadata, self).__init__(*args, **kwargs)
        self.width, self.height = self.get_dimensions()
        self.duration = self.get_duration()
        self.title = self.get_fmt_tags(('title',))
        self.author = self.get_fmt_tags(('author', 'artist'))
        self.description = self.get_fmt_tags(('description', 'comment'))

AudioMetadata = FFmpegAudioVideoMetadata
VideoMetadata = FFmpegAudioVideoMetadata
