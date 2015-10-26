try:
    import __builtin__ as builtins
except ImportError:
    import builtins

from contextlib import contextmanager
from datetime import datetime

import mock
import pytest

import librarian_content.library.metadata as mod


def _has_key(d, name):
    assert name in d


@contextmanager
def key_overrides(obj, **kwargs):
    new_keys = []
    orig_values = {}
    for key, value in kwargs.items():
        if key not in obj:
            new_keys.append(key)
        else:
            orig_values[key] = obj[key]
        obj[key] = value
    yield
    for key in new_keys:
        del obj[key]
    for key, value in orig_values.items():
        obj[key] = value


def test_edge_keys():
    assert sorted(mod.get_edge_keys()) == sorted([
        'language',
        'license',
        'title',
        'url',
        'timestamp',
        'cover',
        'thumbnail',
        'replaces',
        'broadcast',
        'keywords',
        'is_partner',
        'content',
        'publisher',
        'is_sponsored',
        'archive',
    ])


def test_replace_aliases():
    meta = {'url': 'test',
            'title': 'again',
            'is_partner': True,
            'partner': 'Partner'}
    expected = {'url': 'test',
                'title': 'again',
                'is_partner': True,
                'publisher': 'Partner'}
    mod.replace_aliases(meta)
    assert meta == expected


def test_adding_missing_keys():
    """ Metadata keys that are not in ``d`` will be added """
    d = {}
    mod.add_missing_keys(d)
    for key in mod.get_edge_keys():
        _has_key(d, key)


def test_adding_missing_key_doesnt_remove_existing():
    """ Existing keys will be kept """
    d = {'url': 'foo'}
    mod.add_missing_keys(d)
    assert d['url'] == 'foo'


def test_adding_missing_keys_doeesnt_remove_arbitrary_keys():
    """" Even non-standard keys will be kept """
    d = {'foo': 'bar'}
    mod.add_missing_keys(d)
    _has_key(d, 'foo')


def test_add_missing_keys_has_return():
    """ Add missing key mutates the supplies dict, but has no return value """
    d = {}
    ret = mod.add_missing_keys(d)
    assert ret is None


def test_clean_keys():
    """ Removes invalid keys """
    d = {'foo': 'bar', 'title': 'title'}
    mod.clean_keys(d)
    assert d == {'title': 'title'}


@mock.patch.object(mod, 'clean_keys')
@mock.patch.object(mod, 'add_missing_keys')
@mock.patch.object(mod, 'replace_aliases')
@mock.patch.object(mod.validator, 'validate')
def test_process_meta_success(validate, replace_aliases, add_missing_keys,
                              clean_keys):
    meta = {'title': 'test', 'gen': 0}
    validate.return_value = {}
    assert mod.process_meta(meta) == meta
    validate.assert_called_once_with(meta, broadcast=True)
    replace_aliases.assert_called_once_with(meta)
    add_missing_keys.assert_called_once_with(meta)
    clean_keys.assert_called_once_with(meta)


@mock.patch.object(mod, 'clean_keys')
@mock.patch.object(mod, 'add_missing_keys')
@mock.patch.object(mod, 'replace_aliases')
@mock.patch.object(mod.validator, 'validate')
def test_process_meta_fail(validate, replace_aliases, add_missing_keys,
                           clean_keys):
    meta = {'title': 'test', 'gen': 0}
    validate.return_value = {'error': 'some'}
    with pytest.raises(mod.MetadataError):
        mod.process_meta(meta)

    validate.assert_called_once_with(meta, broadcast=True)
    assert not replace_aliases.called
    assert not add_missing_keys.called
    assert not clean_keys.called


@mock.patch.object(mod, 'os', autospec=True)
def test_get_meta_missing(os):
    os.path.exists.return_value = False
    try:
        mod.get_meta('basedir', 'relpath', ['.contentinfo'])
    except mod.ValidationError as exc:
        assert exc.message == 'missing metadata file'
    else:
        pytest.fail('should have raised')


@mock.patch.object(builtins, 'open')
@mock.patch.object(mod, 'os', autospec=True)
def test_get_meta_cannot_open(os, open_fn):
    os.path.exists.return_value = True
    open_fn.side_effect = OSError()
    try:
        mod.get_meta('basedir', 'relpath', ['.contentinfo'])
    except mod.ValidationError as exc:
        assert exc.message == 'metadata file cannot be opened'
    else:
        pytest.fail('should have raised')


@mock.patch.object(builtins, 'open')
@mock.patch.object(mod, 'json', autospec=True)
@mock.patch.object(mod, 'os', autospec=True)
def test_get_meta_cannot_decode(os, json, open_fn):
    os.path.exists.return_value = True
    json.load.side_effect = ValueError()
    try:
        mod.get_meta('basedir', 'relpath', ['.contentinfo'])
    except mod.ValidationError as exc:
        assert exc.message == 'malformed metadata file'
    else:
        pytest.fail('should have raised')


@mock.patch.object(builtins, 'open')
@mock.patch.object(mod, 'process_meta')
@mock.patch.object(mod, 'json', autospec=True)
@mock.patch.object(mod, 'os', autospec=True)
def test_get_meta_cannot_process(os, json, process_meta, open_fn):
    os.path.exists.return_value = True
    process_meta.side_effect = mod.MetadataError('exc message', 'wrong keys')
    try:
        mod.get_meta('basedir', 'relpath', ['.contentinfo'])
    except mod.ValidationError as exc:
        assert exc.message == 'exc message'
    else:
        pytest.fail('should have raised')


@mock.patch.object(mod, 'json', autospec=True)
@mock.patch.object(mod, 'os', autospec=True)
def test_meta_class_init(os, json):
    """ Initializing the Meta class must give the instance correct props """
    os.path.normpath.side_effect = lambda x: x
    data = {'md5': 'test', 'tags': 'tag json data'}
    meta = mod.Meta(data)
    assert meta.meta == data
    assert meta.meta is not data
    json.loads.assert_called_once_with('tag json data')
    assert meta.tags == json.loads.return_value


@mock.patch.object(mod, 'os', autospec=True)
def test_meta_class_init_with_no_tags(*ignored):
    """ Supplying empty string as tags should not cause Meta to raise """
    # Empty strig should not cause ``json.loads()`` to trip
    try:
        meta = mod.Meta({'tags': ''})
        assert meta.tags == {}
    except ValueError:
        assert False, 'Excepted not to raise'


@mock.patch.object(mod, 'json', autospec=True)
@mock.patch.object(mod, 'os', autospec=True)
def test_meta_attribute_access(*ignored):
    """ Attribute access to mod keys should be possible """
    meta = mod.Meta({'foo': 'bar', 'baz': 1})
    assert meta['foo'] == 'bar'
    assert meta.baz == 1


@mock.patch.object(mod, 'json', autospec=True)
def test_meta_attribute_error(json):
    """ AttributeError should be raised on missing key/attribute """
    meta = mod.Meta({})
    try:
        meta.missing
        assert False, 'Expected to raise'
    except AttributeError:
        pass


@mock.patch.object(mod, 'json', autospec=True)
@mock.patch.object(mod, 'os', autospec=True)
def test_meta_set_key(*ignored):
    """ Setting keys using subscript notation is possible """
    data = {}
    meta = mod.Meta(data)
    meta['missing'] = 'not anymore'
    assert meta.missing == 'not anymore'


@mock.patch.object(mod, 'json', autospec=True)
@mock.patch.object(mod, 'os', autospec=True)
def test_meta_set_key_does_not_update_original(*ignored):
    """ The original mod dict is updated when Meta object is updated """
    data = {}
    meta = mod.Meta(data)
    meta['missing'] = 'not anymore'
    assert data == {}


@mock.patch.object(mod, 'json', autospec=True)
@mock.patch.object(mod, 'os', autospec=True)
def test_meta_get_key(*ignored):
    """ Key values can be obtained using ``get()`` method as with dicts """
    meta = mod.Meta({'foo': 'bar'})
    assert meta.get('foo') == 'bar'
    assert meta.get('missing') is None


@mock.patch.object(mod, 'json', autospec=True)
@mock.patch.object(mod, 'os', autospec=True)
def test_lang_property(*ignored):
    """ The lang property is an alias for language key """
    meta = mod.Meta({'language': 'foo'})
    assert meta.lang == 'foo'
    meta['language'] = 'bar'
    assert meta.lang == 'bar'


@mock.patch.object(mod, 'json', autospec=True)
@mock.patch.object(mod, 'os', autospec=True)
def test_lang_with_missing_language(*ignored):
    """ Lang property returns None if there is no language key """
    meta = mod.Meta({})
    assert meta.lang is None


@mock.patch.object(mod, 'json', autospec=True)
@mock.patch.object(mod, 'os', autospec=True)
def test_label_property_default(*ignored):
    """ Label is 'core' if there is no archive key """
    meta = mod.Meta({})
    assert meta.label == 'core'


@mock.patch.object(mod, 'json', autospec=True)
@mock.patch.object(mod, 'os', autospec=True)
def test_label_property_with_keys(*ignored):
    """ Correct label should be returned for appropriate key values """
    meta = mod.Meta({})
    with key_overrides(meta, archive='core'):
        assert meta.label == 'core'
    with key_overrides(meta, is_sponsored=True):
        assert meta.label == 'sponsored'
    with key_overrides(meta, is_partner=True):
        assert meta.label == 'partner'


@mock.patch.object(mod, 'json', autospec=True)
@mock.patch.object(mod, 'os', autospec=True)
def test_label_property_with_key_combinations(*ignored):
    """ Correct label should be returned for appropriate key combos """
    meta = mod.Meta({})
    with key_overrides(meta, archive='core', is_sponsored=True):
        assert meta.label == 'core'
    with key_overrides(meta, archive='ephem', is_sponsored=True):
        assert meta.label == 'sponsored'
    with key_overrides(meta, archive='core', is_partner=True):
        assert meta.label == 'core'
    with key_overrides(meta, archive='ephem', is_partner=True):
        assert meta.label == 'partner'


def test_determine_content_type():
    for name, value in mod.CONTENT_TYPES.items():
        meta = {'content': {name: None}}
        assert mod.determine_content_type(meta) == value

    mixed = {'content': {'app': None, 'generic': None}}
    expected = mod.CONTENT_TYPES['app'] + mod.CONTENT_TYPES['generic']
    assert mod.determine_content_type(mixed) == expected


def test_parse_datetime():
    test = {
        'first': 1,
        'another': '11',
        'second': 'str',
        'third': ['a', {'b': 'fake', 'c': '2012-05-08'}],
        'fourth': {
            'd': '2015-10-16T13:06:01.540391',
            'e': [{
                'g': '2015-10-16T13:06:01.540391'
            }]
        }
    }
    mod.parse_datetime(test)
    assert isinstance(test['first'], int)
    assert isinstance(test['another'], str)
    assert isinstance(test['third'][1]['c'], datetime)
    assert isinstance(test['fourth']['d'], datetime)
    assert isinstance(test['fourth']['e'][0]['g'], datetime)
