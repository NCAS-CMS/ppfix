import configparser
from pathlib import Path
from unittest.mock import patch

import cf
import pytest

from ppfix import fix_atmosphere, process_nemo, rechunk_file


class FakeAxis:
    def __init__(self, name):
        self._name = name

    def nc_get_dimension(self, default=None):
        return self._name if self._name is not None else default

    def nc_set_dimension(self, name):
        self._name = name


class FakeBounds:
    def __init__(self, variable_name):
        self._variable_name = variable_name

    def nc_get_variable(self, default=None):
        return self._variable_name if self._variable_name is not None else default

    def nc_set_variable(self, variable_name):
        self._variable_name = variable_name


class FakeCoordinate:
    def __init__(self, variable_name, bounds=None):
        self._variable_name = variable_name
        self._bounds = bounds

    def nc_get_variable(self, default=None):
        return self._variable_name if self._variable_name is not None else default

    def nc_set_variable(self, variable_name):
        self._variable_name = variable_name

    def get_bounds(self, default=None):
        return self._bounds if self._bounds is not None else default


class FakeCanonicalField:
    def __init__(self, coordinates, axes, variable_name=None):
        self._coordinates = coordinates
        self._axes = axes
        self._variable_name = variable_name

    def coordinates(self, todict=False):
        if todict:
            return self._coordinates
        return tuple(self._coordinates.values())

    def domain_axes(self, todict=False):
        if todict:
            return self._axes
        return tuple(self._axes.values())

    def nc_get_variable(self, default=None):
        return self._variable_name if self._variable_name is not None else default

    def nc_set_variable(self, variable_name):
        self._variable_name = variable_name


def metadata():
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(
        '[General]\nactivity-id = HRCM\n'
        '[simulations]\nensemble = {\'u-dz876\': \'r1i1f1p1\'}\n'
        '[run_specific]\nrunid = u-dz876\n'
        '[model_general]\ngrid_label = gn\n'
        '[model_ocean]\nnominal_resolution = 10 km\n'
        '[model_seaice]\nnominal_resolution = 10 km\n'
        '[model_atmos]\nnominal_resolution = 10 km\n'
        '[output]\ncompress = 0\n'
        'single = true\n'
        'dataset_chunks = 8 MiB\n'
    )
    return parser


def test_applies_metadata_before_writing_sea_ice_fields():
    field = cf.example_field(1)
    writes = []

    with patch.object(rechunk_file.cf, 'read', return_value=[field]), patch.object(
        rechunk_file.cf, 'write', side_effect=lambda fields, filename, **kwargs: writes.append((fields, filename, kwargs))
    ), patch.object(
        rechunk_file, 'get_nemochunking', return_value=None
    ):
        rechunk_file.rechunk_existing_netcdf(
            'input.nc', 'output.nc', metadata(), 'model_seaice', {'single': True}
        )

    assert field.get_property('activity-id') == 'HRCM'
    assert field.get_property('nominal_resolution') == '10 km'
    assert field.get_property('variant_id') == 'r1i1f1p1'
    assert writes[0][1] == 'output.nc'


def test_assigns_variant_id_from_simulations_ensemble_mapping():
    field = cf.example_field(1)

    globals = fix_atmosphere.meta2attr(metadata(), field, 'model_atmos')

    assert field.get_property('variant_id') == 'r1i1f1p1'
    assert 'variant_id' in globals


def test_forwards_custom_write_kwargs():
    field = cf.example_field(1)

    with patch.object(fix_atmosphere.cf, 'read', return_value=[field]), patch.object(
        fix_atmosphere, 'write_field'
    ) as write_field, patch.object(
        fix_atmosphere, 'build_simulation_name', return_value='simulation'
    ), patch.object(fix_atmosphere, 'CMIPIdentifiers', return_value=object()), patch.object(
        fix_atmosphere, 'inspect_field', return_value={
            'cms_table': 'day',
            'temporal_cell_method': 'mean',
            'identity': 'tas',
            'cmip6_variable': 'tas',
            'zonal_cell_method': None,
            'start_date': '19500101',
        }
    ), patch.object(fix_atmosphere, 'get_umchunking', return_value=None), patch.object(
        fix_atmosphere, 'meta2attr', return_value=['activity-id', 'runid', 'grid_label']
    ), patch('pathlib.Path.glob', return_value=[Path('atm.pp')]), patch('pathlib.Path.is_file', return_value=True), patch(
        'pathlib.Path.mkdir'
    ):
        fix_atmosphere.process_atmos(
            'input',
            'output',
            metadata(),
            'model_atmos',
        )

    assert write_field.call_args.kwargs['write_kwargs'] == {
        'compress': 0,
        'single': True,
        'dataset_chunks': '8 MiB',
    }
    assert write_field.call_args.args[0] is field
    assert write_field.call_args.args[3] == Path('output')


def test_strips_numeric_suffixes_from_coordinate_vars_and_dimensions():
    lat_bounds = FakeBounds('latitude_1_bounds')
    lon_bounds = FakeBounds('longitude_1_bounds')
    coords = {
        'dim0': FakeCoordinate('height_2'),
        'dim1': FakeCoordinate('latitude_1', bounds=lat_bounds),
        'dim2': FakeCoordinate('longitude_1', bounds=lon_bounds),
        'dim3': FakeCoordinate('time'),
    }
    axes = {
        'axis0': FakeAxis('height_2'),
        'axis1': FakeAxis('latitude_1'),
        'axis2': FakeAxis('longitude_1'),
        'axis3': FakeAxis('time'),
    }
    field = FakeCanonicalField(coords, axes, variable_name='tas_3')

    fix_atmosphere.canonicalise(field)

    assert coords['dim0'].nc_get_variable() == 'height'
    assert coords['dim1'].nc_get_variable() == 'latitude'
    assert coords['dim2'].nc_get_variable() == 'longitude'
    assert coords['dim3'].nc_get_variable() == 'time'
    assert lat_bounds.nc_get_variable() == 'latitude_bounds'
    assert lon_bounds.nc_get_variable() == 'longitude_bounds'
    assert axes['axis0'].nc_get_dimension() == 'height'
    assert axes['axis1'].nc_get_dimension() == 'latitude'
    assert axes['axis2'].nc_get_dimension() == 'longitude'
    assert axes['axis3'].nc_get_dimension() == 'time'
    assert field.nc_get_variable() == 'tas'


@pytest.mark.parametrize(
    ('target_exists', 'should_call_rechunk'),
    [
        (False, True),
        (True, False),
    ],
)
def test_uses_model_seaice_section_and_does_not_replace_by_default(target_exists, should_call_rechunk):
    with patch.object(process_nemo, 'rechunk_existing_netcdf') as rechunk:
        with patch('pathlib.Path.glob', return_value=[Path('si3_0001.nc')]), patch(
            'pathlib.Path.mkdir'
        ), patch('pathlib.Path.exists', return_value=target_exists):
            process_nemo.process_sice('input', 'output', metadata())

    if should_call_rechunk:
        assert rechunk.call_args.args[3] == 'model_seaice'
        return

    rechunk.assert_not_called()