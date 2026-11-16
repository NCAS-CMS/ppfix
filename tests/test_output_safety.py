import configparser
from pathlib import Path

import cf
import pytest

from ppfix import fix_atmosphere, process_nemo
from ppfix.utils import make_output_file_name


PROPERTIES = {
    'cms_table': 'monthly',
    'start_date': '195002',
    'temporal_cell_method': 'mean',
    'identity': 'surface_temperature',
    'cms_vcoord': 'Z0',
    'cmip6_variable': 'unknown',
    'zonal_cell_method': None,
}


class Field:
    def __init__(self, stash):
        self.stash = stash

    def get_property(self, key, default=None):
        return self.stash if key == 'um_stash_source' else default

    def nc_get_variable(self, default=None):
        return default


@pytest.fixture
def metadata():
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(
        '[General]\nactivity_id = HRCM\nexperiment = spinup\n'
        '[run_specific]\nrunid = udz876\n'
    )
    return parser


def test_collision_names_use_distinct_stash_codes(monkeypatch):
    monkeypatch.setattr(
        fix_atmosphere, 'inspect_field', lambda cmip, field: dict(PROPERTIES)
    )
    properties = fix_atmosphere._prepare_output_properties(
        [Field('m01s00i507'), Field('m01s00i508')], None, 'sim', 'month.pp'
    )
    names = [make_output_file_name('sim', extra) for extra in properties]

    assert len(set(names)) == 2
    assert names[0].endswith('__m01s00i507.nc')
    assert names[1].endswith('__m01s00i508.nc')


def test_unresolved_collision_raises(monkeypatch):
    monkeypatch.setattr(
        fix_atmosphere, 'inspect_field', lambda cmip, field: dict(PROPERTIES)
    )

    with pytest.raises(ValueError, match='Duplicate output filenames'):
        fix_atmosphere._prepare_output_properties(
            [Field('same'), Field('same')], None, 'sim', 'month.pp'
        )


def test_fixed_names_include_source(monkeypatch):
    monkeypatch.setattr(
        fix_atmosphere, 'inspect_field',
        lambda cmip, field: {**PROPERTIES, 'start_date': None},
    )
    names = []
    for source in ('first.pp', 'second.pp'):
        properties = fix_atmosphere._prepare_output_properties(
            [Field('stash')], None, 'sim', source
        )
        names.append(make_output_file_name('sim', properties[0]))

    assert len(set(names)) == 2


def test_normal_name_preserved(monkeypatch):
    monkeypatch.setattr(
        fix_atmosphere, 'inspect_field', lambda cmip, field: dict(PROPERTIES)
    )
    properties = fix_atmosphere._prepare_output_properties(
        [Field('stash')], None, 'sim', 'month.pp'
    )

    assert properties == [PROPERTIES]


def test_write_forces_no_overwrite(monkeypatch):
    calls = []
    field = cf.example_field(0)
    monkeypatch.setattr(Path, 'mkdir', lambda *args, **kwargs: None)
    monkeypatch.setattr(Path, 'exists', lambda *args: False)
    monkeypatch.setattr(
        fix_atmosphere.cf, 'write', lambda *args, **kwargs: calls.append(kwargs)
    )

    fix_atmosphere.write_field(
        field, 'sim', dict(PROPERTIES), '/unused',
        write_kwargs={'overwrite': True},
    )

    assert calls[0]['overwrite'] is False


def test_existing_output_fails_before_write(monkeypatch, metadata):
    monkeypatch.setattr(Path, 'mkdir', lambda *args, **kwargs: None)
    monkeypatch.setattr(Path, 'glob', lambda *args: [Path('month.pp')])
    monkeypatch.setattr(Path, 'is_file', lambda *args: True)
    monkeypatch.setattr(Path, 'exists', lambda *args: True)
    monkeypatch.setattr(
        fix_atmosphere.cf, 'read', lambda *args: [Field('stash')]
    )
    monkeypatch.setattr(
        fix_atmosphere, 'inspect_field', lambda cmip, field: dict(PROPERTIES)
    )
    monkeypatch.setattr(fix_atmosphere, 'CMIPIdentifiers', lambda: None)
    monkeypatch.setattr(
        fix_atmosphere, 'write_field',
        lambda *args, **kwargs: pytest.fail('Unexpected write'),
    )

    with pytest.raises(FileExistsError, match='Refusing to overwrite'):
        fix_atmosphere.process_atmos(
            '/input', '/output', metadata, 'model_atmos'
        )


@pytest.mark.parametrize(
    ('processor', 'source'),
    [
        (process_nemo.process_ocean, 'nemo_run_1m_grid.nc'),
        (process_nemo.process_sice, 'si3_run_1m_grid.nc'),
    ],
)
def test_ocean_and_seaice_writes_disable_replacement(
    monkeypatch, metadata, processor, source
):
    calls = []
    monkeypatch.setattr(Path, 'mkdir', lambda *args, **kwargs: None)
    monkeypatch.setattr(Path, 'glob', lambda *args: [Path(source)])
    monkeypatch.setattr(Path, 'exists', lambda *args: False)
    monkeypatch.setattr(
        process_nemo, 'rechunk_existing_netcdf',
        lambda *args, **kwargs: calls.append(kwargs),
    )

    processor('/input', '/output', metadata, False)

    assert calls[0]['kwchoices']['overwrite'] is False
