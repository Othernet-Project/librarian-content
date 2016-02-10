import os
import logging

import mutagen.mp3
from PIL import Image
from iptcinfo import IPTCInfo

from fsal.client import OpenError


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


class FacetProcessorBase(object):
    def __init__(self, fsal, basepath):
        self.fsal = fsal
        self.basepath = basepath

    def add_file(self, facets, relpath):
        pass

    def remove_file(self, facets, relpath):
        pass

    def update_file(self, facets, relpath):
        pass

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
        facets['generic'] = {'path': relpath}

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

    def add_file(self, facets, relpath):
        if 'html' in facets:
            index_name = os.path.basename(facets['html']['index'])
            if 'index' in index_name:
                # Nothing to do anymore
                return
        self._find_index(facets)

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

    EXIF_TITLE_TAG = 270

    def get_image_metadata(self, relpath):
        path = os.path.join(self.basepath, relpath)
        title = None
        try:
            with self.fsal.open(path, 'rb') as f:
                width, height = Image.open(f).size
            with self.fsal.open(path, 'rb') as f:
                title_exif = self._get_image_metadata_exif(f)
        except OpenError:
            # File no longer exists on the storage(s). Do nothing
            pass

        title = title_exif or ''
        return {
            'file': relpath,
            'title': title,
            'width': width,
            'height': height
        }

    def add_file(self, facets, relpath):
        image_f = facets.get('image', dict())
        gallery = image_f.get('gallery', list())
        for meta in gallery:
            if meta['file'] == relpath:
                self.update_file(facets, relpath)
                return
        else:
            image_metadata = self.get_image_metadata(relpath)
            gallery.append(image_metadata)
            facets['image'] = { 'gallery': gallery }

    def remove_file(self, facets, relpath):
        image_f = facets.get('image', dict())
        gallery = image_f.get('gallery', list())
        gallery[:] = [entry for entry in gallery if entry['file'] != relpath]
        facets['image'] = { 'gallery': gallery }

    def _get_image_metadata_exif(self, fileobj):
        title = ''
        try:
            image = Image.open(fileobj)
            if image.format in ['JPG', 'TIFF']:
                exif_data = image._getexif()
                if exif_data:
                    title = exif_data.get(self.EXIF_TITLE_TAG, '')
        except IOError:
            # File no longer exists do nothing
            pass
        return title

    def _get_image_metadata_iptc(self, fileobj):
        title = ''
        try:
            image = IPTCInfo(fileobj)
            data = image.data
            title = data.get('object name', '') or data.get('headline', '')
        except Exception:
            # IPTC data not found
            pass
        finally:
            return title


class AudioFacetProcessor(FacetProcessorBase):
    EXTENSIONS = ['mp3']

    def get_audio_metadata(self, relpath):
        artist = ''
        title = ''
        duration = 0
        ext = get_extension(relpath)
        if ext == 'mp3':
            artist, title, duration = self._get_mp3_metadata(relpath)
        return {
            'file': relpath,
            'artist': artist,
            'title': title,
            'duration': duration
        }

    def add_file(self, facets, relpath):
        audio_facet = facets.get('audio', dict())
        playlist = audio_facet.get('playlist', list())
        for f in playlist:
            if f['file'] == relpath:
                self.update_file(facets, relpath)
                return
        else:
            audio_metadata = self.get_audio_metadata(relpath)
            playlist.append(audio_metadata)
            facets['audio'].update({ 'playlist': playlist })

    def remove_file(self, facets, relpath):
        audio_facet = facets.get('audio', dict())
        playlist = audio_facet.get('playlist', list())
        playlist[:] = [entry for entry in playlist if entry['file'] != relpath]
        facets['audio'] = { 'playlist': playlist }

    def _get_mp3_metadata(self, relpath):
        artist, title, duration = ('', '', 0)
        success, fso = self.fsal.get_fso(relpath)
        if success:
            mp3 = mutagen.mp3.MP3(fso.path)
            duration = mp3.info.length
            #TODO Use fallback tags
            id3_tope = mp3.tags.get('TOPE')
            id3_tit2 = mp3.tags.get('TIT2')
            artist = id3_tope[0] if id3_tope else ''
            title = id3_tit2[0] if id3_tit2 else ''
        return (artist, title, duration)
