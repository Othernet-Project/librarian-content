import os
import functools

from .metadata import ImageMetadata, AudioMetadata, VideoMetadata

def split_name(fname):
    name, ext = os.path.splitext(fname)
    ext = ext[1:].lower()
    return name, ext


def get_extension(fname):
    _, ext = split_name(fname)
    return ext


def strip_extension(fname):
    name, _ = split_name(fname)
    return name


def get_facet_processors(fsal, dir_path, file_path):
    all_processors =  FacetProcessorBase.__subclasses__()
    valid_processors = []
    for processor in all_processors:
        if processor.can_process(dir_path, file_path):
            valid_processors.append(processor(fsal, dir_path))
    return valid_processors


#TODO: Remove this after facets become stable
def log_facets(prefix, facets):
    import pprint
    import logging
    logging.debug('{} {}'.format(prefix, pprint.pformat(dict(facets))))


def cleanup(func):
    @functools.wraps(func)
    def wrapper(self, facets, path):
        result = func(self, facets, path)
        _cleanup(facets)
        return result
    return wrapper


def _cleanup(data):
    for key, value in data.items():
        if isinstance(value, list):
            for row in value:
                _cleanup(row)
            value[:] = [row for row in value if row]
            if not value:
                del data[key]
        elif isinstance(value, dict):
            _cleanup(value)
            if not value:
                del data[key]


class FacetProcessorBase(object):
    def __init__(self, fsal, basepath):
        self.fsal = fsal
        self.basepath = basepath

    def add_file(self, facets, relpath):
        raise NotImplementedError()

    def remove_file(self, facets, relpath):
        raise NotImplementedError()

    def update_file(self, facets, relpath):
        raise NotImplementedError()

    @classmethod
    def can_process(cls, basepath, relpath):
        if hasattr(cls, 'EXTENSIONS'):
            extensions = list(getattr(cls, 'EXTENSIONS'))
            return get_extension(relpath) in extensions
        return False


class GenericFacetProcessor(FacetProcessorBase):

    def add_file(self, facets, relpath):
        return self._process(facets, relpath)

    def remove_file(self, facets, relpath):
        return self._process(facets, relpath)

    def update_file(self, facets, relpath):
        return self._process(facets, relpath)

    def _process(self, facets, relpath):
        facets['generic'] = {'path': self.basepath}

    @classmethod
    def can_process(cls, basepath, relpath):
        return True


class HtmlFacetProcessor(FacetProcessorBase):
    EXTENSIONS = ['html', 'htm']

    INDEX_NAMES = {
        'index': 1,
        'main':  2,
        'start': 3,
    }

    @cleanup
    def add_file(self, facets, relpath):
        if 'html' in facets:
            index_name = os.path.basename(facets['html']['index'])
            if 'index' in index_name:
                # Nothing to do anymore
                return
        self._find_index(facets)

    def update_file(self, facets, relpath):
        pass

    @cleanup
    def remove_file(self, facets, relpath):
        if facets['html']['index'] == relpath:
            del facets['html']
            self._find_index(facets)

    def _find_index(self, facets):
        (success, dirs, files) = self.fsal.list_dir(facets['path'])
        index_path = None
        path_priority = 100
        html_count = 0
        first_html_file = None
        files = filter(lambda f: get_extension(f.name) in self.EXTENSIONS, files)
        for f in files:
            name, ext = split_name(f.name)
            if name in self.INDEX_NAMES.keys():
                first_html_file = first_html_file or f.rel_path
                priority = self.INDEX_NAMES[name]
                if path_priority < priority:
                    index_path = f.rel_path
                    path_priority = priority
            html_count += 1

        if not index_path and html_count > 0:
            index_path = first_html_file

        if index_path:
            index_path = os.path.relpath(index_path, self.basepath)
            facets['html'] = { 'index': index_path }


class ImageFacetProcessor(FacetProcessorBase):
    EXTENSIONS = ['jpg', 'jpeg', 'png']

    @cleanup
    def add_file(self, facets, relpath):
        image_metadata = self._get_metadata(relpath)
        gallery = self._get_gallery(facets)
        gallery.append(image_metadata)

    @cleanup
    def update_file(self, facets, relpath):
        image_metadata = self._get_metadata(relpath)
        gallery = self._get_gallery(facets)
        for entry in gallery:
            if entry['file'] == relpath:
                entry.update(image_metadata)
                return

    @cleanup
    def remove_file(self, facets, relpath):
        gallery = self._get_gallery(facets)
        gallery = [entry for entry in gallery if entry['file'] != relpath]

    def _get_gallery(self, facets):
        if 'image' not in facets:
            facets['image'] = {'gallery':list()}
        elif 'gallery' not in facets['image']:
            facets['image']['gallery'] = list()
        return facets['image']['gallery']

    def _get_metadata(self, relpath):
        path = os.path.join(self.basepath, relpath)
        meta = ImageMetadata(self.fsal, path)
        return {
            'file': relpath,
            'title': meta.get('title', ''),
            'width': meta.get('width', 0),
            'height': meta.get('height', 0)
        }


class AudioFacetProcessor(FacetProcessorBase):
    EXTENSIONS = ['mp3']


    @cleanup
    def add_file(self, facets, relpath):
        audio_metadata = self._get_metadata(relpath)
        playlist = self._get_playlist(facets)
        playlist.append(audio_metadata)

    @cleanup
    def update_file(self, facets, relpath):
        audio_metadata = self._get_metadata(relpath)
        playlist = self._get_playlist(facets)
        for entry in playlist:
            if entry['file'] == relpath:
                entry.update(audio_metadata)
                return

    @cleanup
    def remove_file(self, facets, relpath):
        playlist = self._get_playlist(facets)
        playlist = [entry for entry in playlist if entry['file'] != relpath]

    def _get_playlist(self, facets):
        if 'audio' not in facets:
            facets['audio'] = {'playlist':list()}
        elif 'playlist' not in facets['audio']:
            facets['audio']['playlist'] = list()
        return facets['audio']['playlist']

    def _get_metadata(self, relpath):
        path = os.path.join(self.basepath, relpath)
        meta = AudioMetadata(self.fsal, path)
        return {
            'file': relpath,
            'artist': meta.get('artist', ''),
            'title': meta.get('title', ''),
            'duration': meta.get('duration', 0)
        }


class VideoFacetProcessor(FacetProcessorBase):
    EXTENSIONS = ['mp4', 'wmv', 'webm', 'flv', 'ogv']

    @cleanup
    def add_file(self, facets, relpath):
        video_metadata = self._get_metadata(relpath)
        clips = self._get_clips(facets)
        clips.append(video_metadata)

    @cleanup
    def update_file(self, facets, relpath):
        video_metadata = self._get_metadata(relpath)
        clips = self._get_clips(facets)
        for entry in clips:
            if entry['file'] == relpath:
                entry.update(video_metadata)
                return

    @cleanup
    def remove_file(self, facets, relpath):
        clips = self._get_clips(facets)
        clips = [entry for entry in clips if entry['file'] != relpath]

    def _get_clips(self, facets):
        if 'video' not in facets:
            facets['video'] = {'clips':list()}
        elif 'clips' not in facets['video']:
            facets['video']['clips'] = list()
        return facets['video']['clips']

    def _get_metadata(self, relpath):
        path = os.path.join(self.basepath, relpath)
        meta = ImageMetadata(self.fsal, path)
        return {
            'file': relpath,
            'title': meta.get('title', ''),
            'width': meta.get('width', 0),
            'height': meta.get('height', 0),
            'duration': meta.get('duration', 0),
            #TODO: Thumbnail generation
            'thumbnail': '',
        }
