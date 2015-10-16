import datetime
import os

import mock
import pytest

import librarian_content.library.content as mod


MOD = mod.__name__


@mock.patch.object(mod.scandir, 'scandir')
def test_filewalk(scandir):
    mocked_dir = mock.Mock()
    mocked_dir.is_dir.return_value = True
    mocked_dir.path = '/path/dir/'

    mocked_file = mock.Mock()
    mocked_file.is_dir.return_value = False
    mocked_file.path = '/path/dir/file.ext'

    root_dir = '/path/'

    def mocked_scandir(path):
        if path == root_dir:
            yield mocked_dir
        else:
            yield mocked_file

    scandir.side_effect = mocked_scandir
    assert list(mod.filewalk(root_dir)) == ['/path/dir/file.ext']


def test_find_content_dir(md5dirs):
    """ Should return only well-formed MD5-base paths """
    hashes, dirs, tmpdir = md5dirs
    bogus_dirs = [os.path.join(tmpdir, n) for n in ['abc',
                                                    'foo',
                                                    'bar',
                                                    'baz']]
    for d in bogus_dirs:
        os.makedirs(d)

    for d in dirs:
        os.makedirs(os.path.join(d, 'abc'))  # add subdirectories into content

    ret = list(mod.find_content_dirs(tmpdir, ['.contentinfo'], relative=False))
    dirs.sort()
    ret.sort()
    assert ret == dirs


@mock.patch.object(mod.metadata, 'upgrade_meta')
def test_get_meta(upgrade_meta, metadata_dir, metadata):
    """ Load and parse metadata from md5-based dir stcture under base dir """
    md5, tmpdir = metadata_dir
    ret = mod.get_meta(tmpdir, md5, ['.contentinfo', 'info.json'])
    for key, expected in metadata.items():
        got = ret[key]
        if not isinstance(got, datetime.datetime):
            assert expected == got


def test_get_meta_with_missing_metadta(md5dirs):
    hashes, dirs, tmpdir = md5dirs
    md5 = hashes[0]
    with pytest.raises(mod.ValidationError):
        mod.get_meta(tmpdir, md5, ['.contentinfo'])


def test_get_meta_with_bad_metadta(bad_metadata_dir, metadata):
    md5, tmpdir = bad_metadata_dir
    with pytest.raises(mod.ValidationError):
        mod.get_meta(tmpdir, md5, ['metafile'])


@mock.patch.object(mod, 'filewalk')
@mock.patch('os.stat')
def test_get_content_size(stat, filewalk):
    mocked_stat = mock.Mock(st_size=1024)
    stat.return_value = mocked_stat
    filewalk.return_value = ['basedir/relpath/a', 'basedir/relpath/b']
    assert mod.get_content_size('basedir', 'relpath') == 2048
    calls = [mock.call('basedir/relpath/a'),
             mock.call('basedir/relpath/b')]
    stat.assert_has_calls(calls)
    filewalk.assert_called_once_with('basedir/relpath')
