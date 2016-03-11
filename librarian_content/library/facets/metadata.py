from __future__ import unicode_literals

import json
import gevent
import logging
import datetime
import subprocess

from bottle_utils.common import to_unicode


FFPROBE_CMD = 'ffprobe -v quiet -i HOLDER1 -show_entries HOLDER2 -print_format json'


def run_command(command, timeout, debug=False):
    start = datetime.datetime.now()
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    if debug:
        logging.debug(
            'Command ({}) started at pid {}'.format(
                ' '.join(command), process.pid))
    while process.poll() is None:
        gevent.sleep(0.1)
        now = datetime.datetime.now()
        if (now - start).seconds > timeout:
            if debug:
                logging.debug(
                    'Command ({}) ran past timeout of {} secs and'
                    ' will be terminated'.format(' '.join(command), timeout))
            process.kill()
            return None
    if debug:
        logging.debug(
            'Command with pid {} ended normally with return code {}'.format(
                process.pid, process.returncode))
    return (process.returncode, process.stdout.read())


def build_ffprobe_command(path, entries=('format', 'streams')):
    show_entries = ':'.join(entries)
    command = FFPROBE_CMD.split(' ')
    command[4] = path
    command[6] = show_entries
    return command


class BaseMetadata(object):

    def __init__(self, fsal, path):
        self.fsal = fsal
        self.path = to_unicode(path)

    def get(self, key, default=None):
        raise NotImplementedError()


class FFmpegMetadataWrapper(BaseMetadata):

    ENTRIES = ('format', 'streams')

    def __init__(self, *args, **kwargs):
        entries = kwargs.pop('entries', self.ENTRIES)
        super(FFmpegMetadataWrapper, self).__init__(*args, **kwargs)

        success, fso = self.fsal.get_fso(self.path)
        if not success:
            msg = u'Error while extracting metadata: No such file: {}'.format(
                self.path)
            logging.error(msg)
            raise IOError(msg)
        command = build_ffprobe_command(fso.path, entries=entries)
        (ret, output) = run_command(command, timeout=5)
        if not output:
            msg = u'Error extracting metadata: Extraction timedout or failed'
            raise IOError(msg)
        try:
            self.data = json.loads(output)
        except ValueError:
            msg = u'Error extracting metadata: JSON expected, got {}'.format(
                type(output))
            raise IOError(msg)

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

    def get_format_tag(self, tags, default=''):
        fmt = self.data.get('format', dict())
        format_tags = fmt.get('tags', dict())
        for tag in tags:
            if tag in format_tags:
                return format_tags[tag]
        return default


class FFmpegImageMetadata(FFmpegMetadataWrapper):

    ENTRIES = ('frames',)

    def __init__(self, *args, **kwargs):
        kwargs['entries'] = self.ENTRIES
        super(FFmpegImageMetadata, self).__init__(*args, **kwargs)

        self.width, self.height = self.get_dimensions()
        self.title = self.get_frames_tag(('title', 'ImageDescription'))

    def get_dimensions(self):
        width = self.get_frames_tag(('width',), 0)
        height = self.get_frames_tag(('height',), 0)
        return width, height

    def get_frames_tag(self, tags, default=''):
        frames = self.data.get('frames', [])
        for frame in frames:
            frame_tags = frame.get('tags', dict())
            for tag in tags:
                if tag in frame_tags:
                    return frame_tags[tag]
        return default


class FFmpegAudioVideoMetadata(FFmpegMetadataWrapper):

    def __init__(self, *args, **kwargs):
        super(FFmpegAudioVideoMetadata, self).__init__(*args, **kwargs)
        self.width, self.height = self.get_dimensions()
        self.duration = self.get_duration()
        self.title = self.get_format_tag(('title',))
        self.author = self.get_format_tag(('author', 'artist'))
        self.description = self.get_format_tag(('description', 'comment'))

    def get_dimensions(self):
        streams = self.data.get('streams', list())
        width, height = (0, 0)
        for stream in streams:
            width = stream.get('width', width)
            height = stream.get('height', height)
        return width, height

ImageMetadata = FFmpegImageMetadata
AudioMetadata = FFmpegAudioVideoMetadata
VideoMetadata = FFmpegAudioVideoMetadata
