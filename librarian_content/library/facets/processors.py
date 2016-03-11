import os
import functools

from .metadata import runnable, ImageMetadata, AudioMetadata, VideoMetadata


IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png']


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


def is_image_file(fname):
    ext = get_extension(fname)
    return ext in IMAGE_EXTENSIONS


def get_facet_processors(fsal, dir_path, file_path):
    all_processors = FacetProcessorBase.__subclasses__()
    valid_processors = []
    for processor in all_processors:
        if processor.can_process(dir_path, file_path):
            valid_processors.append(processor(fsal, dir_path))
    return valid_processors


# TODO: Remove this after facets become stable
def log_facets(prefix, facets):
    import pprint
    import logging
    logging.debug('{} {}'.format(prefix, pprint.pformat(dict(facets))))


def cleanup(func):
    @functools.wraps(func)
    def wrapper(self, facets, path, *args, **kwargs):
        result = func(self, facets, path, *args, **kwargs)
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
    name = None

    def __init__(self, fsal, basepath):
        if self.name is None:
            raise TypeError("Usage of abstract processor is not allowed."
                            "`name` attribute must be defined.")
        self.fsal = fsal
        self.basepath = basepath

    def add_file(self, facets, relpath, partial=False):
        raise NotImplementedError()

    def remove_file(self, facets, relpath):
        raise NotImplementedError()

    def update_file(self, facets, relpath, partial=False):
        raise NotImplementedError()

    @classmethod
    def can_process(cls, basepath, relpath):
        if hasattr(cls, 'EXTENSIONS'):
            extensions = list(getattr(cls, 'EXTENSIONS'))
            return get_extension(relpath) in extensions
        return False

    @classmethod
    def get_processor(cls, path):
        ext = get_extension(path)
        for processor_cls in cls.subclasses():
            if ext in getattr(processor_cls, 'EXTENSIONS', []):
                return processor_cls
        raise RuntimeError("No processor found for the given type.")

    @classmethod
    def subclasses(cls, source=None):
        source = source or cls
        result = source.__subclasses__()
        for child in result:
            result.extend(cls.subclasses(source=child))
        return result

    @staticmethod
    def contains(entries, path):
        for entry in entries:
            if entry['file'] == path:
                return True
        return False

    @staticmethod
    def determine_thumb_path(imgpath, thumbdir, extension):
        imgdir = os.path.dirname(imgpath)
        filename = os.path.basename(imgpath)
        (name, _) = os.path.splitext(filename)
        newname = '.'.join([name, extension])
        return os.path.join(imgdir, thumbdir, newname)

    @classmethod
    def create_thumb(cls, srcpath, thumbpath, root, size, quality,
                     callback=None, default=None):
        if os.path.exists(thumbpath):
            return

        thumbdir = os.path.dirname(thumbpath)
        if not os.path.exists(thumbdir):
            os.makedirs(thumbdir)

        (width, height) = map(int, size.split('x'))
        (ret, _) = cls.generate_thumb(srcpath,
                                      thumbpath,
                                      width=width,
                                      height=height,
                                      quality=quality)
        result = os.path.relpath(thumbpath, root) if ret == 0 else default
        if callback:
            callback(srcpath, result)

        return result


class GenericFacetProcessor(FacetProcessorBase):
    name = 'generic'

    def add_file(self, facets, relpath, partial=False):
        return self._process(facets, relpath)

    def remove_file(self, facets, relpath):
        return self._process(facets, relpath)

    def update_file(self, facets, relpath, partial=False):
        return self._process(facets, relpath)

    def _process(self, facets, relpath):
        facets['generic'] = {'path': self.basepath}

    @classmethod
    def can_process(cls, basepath, relpath):
        return True


class HtmlFacetProcessor(FacetProcessorBase):
    name = 'html'

    EXTENSIONS = ['html', 'htm']

    INDEX_NAMES = {
        'index': 1,
        'main':  2,
        'start': 3,
    }

    @cleanup
    def add_file(self, facets, relpath, partial=False):
        if 'html' in facets:
            index_name = os.path.basename(facets['html']['index'])
            if 'index' in index_name:
                # Nothing to do anymore
                return
        self._find_index(facets)

    def update_file(self, facets, relpath, partial=False):
        pass

    @cleanup
    def remove_file(self, facets, relpath):
        if 'html' in facets and facets['html']['index'] == relpath:
            del facets['html']
            self._find_index(facets)

    def _find_index(self, facets):
        (success, dirs, files) = self.fsal.list_dir(facets['path'])
        index_path = None
        path_priority = 100
        html_count = 0
        first_html_file = None
        files = filter(
            lambda f: get_extension(f.name) in self.EXTENSIONS, files)
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
            facets['html'] = {'index': index_path}


class ImageFacetProcessor(FacetProcessorBase):
    name = 'image'

    EXTENSIONS = IMAGE_EXTENSIONS

    @cleanup
    def add_file(self, facets, relpath, partial=False):
        gallery = self._get_gallery(facets)
        if self.contains(gallery, relpath):
            self.update_file(facets, relpath, partial)
        else:
            image_metadata = self._get_metadata(relpath, partial)
            gallery.append(image_metadata)

    @cleanup
    def update_file(self, facets, relpath, partial=False):
        image_metadata = self._get_metadata(relpath, partial)
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
            facets['image'] = {'gallery': list()}
        elif 'gallery' not in facets['image']:
            facets['image']['gallery'] = list()
        return facets['image']['gallery']

    def _get_metadata(self, relpath, partial):
        if partial:
            return {'file': relpath}
        try:
            path = os.path.join(self.basepath, relpath)
            meta = ImageMetadata(self.fsal, path)
            return {
                'file': relpath,
                'title': meta.title,
                'width': meta.width,
                'height': meta.height
            }
        except IOError:
            return dict()

    @staticmethod
    @runnable()
    def generate_thumb(src, dest, width, height, quality, **kwargs):
        return [
            "ffmpeg",
            "-i",
            src,
            "-q:v",
            str(quality),
            "-vf",
            "scale='if(gt(in_w,in_h),-1,{height})':'if(gt(in_w,in_h),{width},-1)',crop={width}:{height}".format(width=width, height=height),  # NOQA
            dest
        ]


class AudioFacetProcessor(FacetProcessorBase):
    name = 'audio'

    EXTENSIONS = ['mp3', 'wav', 'ogg']

    ALBUMART_NAMES = ['art', 'album', 'cover']

    @cleanup
    def add_file(self, facets, relpath, partial=False):
        playlist = self._get_playlist(facets)
        if self.contains(playlist, relpath):
            self.update_file(facets, relpath, partial)
        else:
            audio_metadata = self._get_metadata(relpath, partial)
            playlist.append(audio_metadata)
            self.scan_cover(facets, playlist)

    @cleanup
    def update_file(self, facets, relpath, partial=False):
        audio_metadata = self._get_metadata(relpath, partial)
        playlist = self._get_playlist(facets)
        for entry in playlist:
            if entry['file'] == relpath:
                entry.update(audio_metadata)
                return

    @cleanup
    def remove_file(self, facets, relpath):
        if is_image_file(relpath):
            self.clear_cover(facets, relpath)
        playlist = self._get_playlist(facets)
        playlist = [entry for entry in playlist if entry['file'] != relpath]
        self.scan_cover(facets, playlist)

    def scan_cover(self, facets, playlist):
        def index(name):
            name = name.lower()
            for i, n in enumerate(self.ALBUMART_NAMES):
                if n in name:
                    return i
            return len(self.ALBUMART_NAMES)

        if len(playlist) == 0:
            self.clear_cover(facets)
            return
        success, dirs, files = self.fsal.list_dir(self.basepath)
        if not success:
            return
        files = filter(lambda f: is_image_file(f.name), files)
        best = len(self.ALBUMART_NAMES)
        cover = ''
        for f in files:
            idx = index(f.name)
            if idx < best:
                best = idx
                cover = f.name
        if cover:
            audio_facet = self._get_audio_facet(facets)
            audio_facet['cover'] = cover

    def clear_cover(self, facets):
        if 'audio' in facets:
            audio_facet = facets['audio']
            if 'cover' in audio_facet:
                del audio_facet['facet']

    def _get_audio_facet(self, facets):
        if 'audio' not in facets:
            facets['audio'] = dict()
        return facets['audio']

    def _get_playlist(self, facets):
        audio_facet = self._get_audio_facet(facets)
        if 'playlist' not in audio_facet:
            audio_facet['playlist'] = list()
        return audio_facet['playlist']

    def _get_metadata(self, relpath, partial):
        if partial:
            return {'file': relpath}
        try:
            path = os.path.join(self.basepath, relpath)
            meta = AudioMetadata(self.fsal, path)
            return {
                'file': relpath,
                'author': meta.author,
                'title': meta.title,
                'duration': meta.duration
            }
        except IOError:
            return dict()

    @staticmethod
    @runnable()
    def generate_thumb(src, dest, **kwargs):
        return [
            "ffmpeg",
            "-i",
            src,
            "-an",
            "-vcodec",
            "copy",
            dest
        ]


class VideoFacetProcessor(FacetProcessorBase):
    name = 'video'

    EXTENSIONS = ['mp4', 'wmv', 'webm', 'flv', 'ogv']

    @cleanup
    def add_file(self, facets, relpath, partial=False):
        clips = self._get_clips(facets)
        if self.contains(clips, relpath):
            self.update_file(facets, relpath, partial)
        else:
            video_metadata = self._get_metadata(relpath, partial)
            clips.append(video_metadata)

    @cleanup
    def update_file(self, facets, relpath, partial=False):
        video_metadata = self._get_metadata(relpath, partial)
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
            facets['video'] = {'clips': list()}
        elif 'clips' not in facets['video']:
            facets['video']['clips'] = list()
        return facets['video']['clips']

    def _get_metadata(self, relpath, partial):
        if partial:
            return {'file': relpath}
        try:
            path = os.path.join(self.basepath, relpath)
            meta = VideoMetadata(self.fsal, path)
            return {
                'file': relpath,
                'title': meta.title,
                'author': meta.author,
                'description': meta.description,
                'width': meta.width,
                'height': meta.height,
                'duration': meta.duration,
                # TODO: Thumbnail generation
                'thumbnail': '',
            }
        except IOError:
            return dict()

    @staticmethod
    @runnable()
    def generate_thumb(src, dest, skip_secs=3, **kwargs):
        return [
            "ffmpeg",
            "-ss",
            str(skip_secs),
            "-i",
            src,
            "-vf",
            "select=gt(scene\,0.5)",
            "-frames:v",
            "1",
            "-vsync",
            "vfr",
            dest
        ]

