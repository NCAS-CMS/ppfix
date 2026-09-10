import configparser
from pathlib import Path
import unittest
from unittest.mock import patch

import cf

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
    def __init__(self, coordinates, axes):
        self._coordinates = coordinates
        self._axes = axes

    def coordinates(self, todict=False):
        if todict:
            return self._coordinates
        return tuple(self._coordinates.values())

    def domain_axes(self, todict=False):
        if todict:
            return self._axes
        return tuple(self._axes.values())


def metadata():
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(
        '[General]\nactivity-id = HRCM\n'
        '[run_specific]\nrunid = u-dz876\n'
        '[model_general]\ngrid_label = gn\n'
        '[model_ocean]\nnominal_resolution = 10 km\n'
        '[model_seaice]\nnominal_resolution = 10 km\n'
        '[output]\ncompress = 0\n'
        'single = true\n'
        'dataset_chunks = 8 MiB\n'
    )
    return parser


class RechunkExistingNetcdfTests(unittest.TestCase):
    def test_applies_metadata_before_writing_sea_ice_fields(self):
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

        self.assertEqual(field.get_property('activity-id'), 'HRCM')
        self.assertEqual(field.get_property('nominal_resolution'), '10 km')
        self.assertEqual(writes[0][1], 'output.nc')


class ProcessAtmosTests(unittest.TestCase):
    def test_forwards_custom_write_kwargs(self):
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

        self.assertEqual(write_field.call_args.kwargs['write_kwargs'], {
            'compress': 0,
            'single': True,
            'dataset_chunks': '8 MiB',
        })
        self.assertIs(write_field.call_args.args[0], field)
        self.assertEqual(write_field.call_args.args[3], Path('output'))


class CanonicaliseTests(unittest.TestCase):
    def test_strips_numeric_suffixes_from_coordinate_vars_and_dimensions(self):
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
        field = FakeCanonicalField(coords, axes)

        fix_atmosphere.canonicalise(field)

        self.assertEqual(coords['dim0'].nc_get_variable(), 'height')
        self.assertEqual(coords['dim1'].nc_get_variable(), 'latitude')
        self.assertEqual(coords['dim2'].nc_get_variable(), 'longitude')
        self.assertEqual(coords['dim3'].nc_get_variable(), 'time')
        self.assertEqual(lat_bounds.nc_get_variable(), 'latitude_bounds')
        self.assertEqual(lon_bounds.nc_get_variable(), 'longitude_bounds')
        self.assertEqual(axes['axis0'].nc_get_dimension(), 'height')
        self.assertEqual(axes['axis1'].nc_get_dimension(), 'latitude')
        self.assertEqual(axes['axis2'].nc_get_dimension(), 'longitude')
        self.assertEqual(axes['axis3'].nc_get_dimension(), 'time')


class ProcessSeaIceTests(unittest.TestCase):
    def test_uses_model_seaice_section_and_does_not_replace_by_default(self):
        with self.subTest('new output'):
            with unittest.mock.patch.object(process_nemo, 'rechunk_existing_netcdf') as rechunk:
                with unittest.mock.patch('pathlib.Path.glob', return_value=[Path('si3_0001.nc')]), unittest.mock.patch(
                    'pathlib.Path.mkdir'
                ), unittest.mock.patch('pathlib.Path.exists', return_value=False):
                    process_nemo.process_sice('input', 'output', metadata())

            self.assertEqual(rechunk.call_args.args[3], 'model_seaice')

        with self.subTest('existing output'):
            with unittest.mock.patch.object(process_nemo, 'rechunk_existing_netcdf') as rechunk:
                with unittest.mock.patch('pathlib.Path.glob', return_value=[Path('si3_0001.nc')]), unittest.mock.patch(
                    'pathlib.Path.mkdir'
                ), unittest.mock.patch('pathlib.Path.exists', return_value=True):
                    process_nemo.process_sice('input', 'output', metadata())

            rechunk.assert_not_called()


if __name__ == '__main__':
    unittest.main()