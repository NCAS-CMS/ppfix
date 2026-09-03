import configparser
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ppfix import fix_atmosphere, process_nemo, rechunk_file


class FakeField:
    def __init__(self):
        self.properties = {}
        self.data = SimpleNamespace(rechunk=lambda *args, **kwargs: None)

    def set_property(self, key, value):
        self.properties[key] = value

    def get_property(self, key, default=None):
        return self.properties.get(key, default)

    def nc_set_dataset_chunksizes(self, chunks):
        self.chunks = chunks

    def identity(self):
        return 'test-field'


def metadata():
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(
        '[General]\nactivity-id = HRCM\n'
        '[run_specific]\nrunid = u-dz876\n'
        '[model_general]\ngrid_label = gn\n'
        '[model_ocean]\nnominal_resolution = 10 km\n'
        '[model_seaice]\nnominal_resolution = 10 km\n'
    )
    return parser


class RechunkExistingNetcdfTests(unittest.TestCase):
    def test_applies_metadata_before_writing_sea_ice_fields(self):
        field = FakeField()
        writes = []
        fake_cf = SimpleNamespace(
            read=lambda filename: [field],
            write=lambda fields, filename, **kwargs: writes.append((fields, filename, kwargs)),
        )

        with patch.object(rechunk_file, 'cf', fake_cf), patch.object(
            rechunk_file, 'get_nemochunking', return_value=None
        ):
            rechunk_file.rechunk_existing_netcdf(
                'input.nc', 'output.nc', metadata(), 'model_seaice', {'single': True}
            )

        self.assertEqual(field.properties['activity-id'], 'HRCM')
        self.assertEqual(field.properties['nominal_resolution'], '10 km')
        self.assertEqual(writes[0][1], 'output.nc')


class ProcessAtmosTests(unittest.TestCase):
    def test_forwards_custom_write_kwargs(self):
        field = FakeField()
        writes = []
        fake_cf = SimpleNamespace(
            read=lambda filename: [field],
            write=lambda field_obj, dataset_name, **kwargs: writes.append((dataset_name, kwargs)),
        )

        with patch.object(fix_atmosphere, 'cf', fake_cf), patch.object(
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
            fix_atmosphere, 'meta2attr'
        ), patch('pathlib.Path.glob', return_value=[Path('atm.pp')]), patch('pathlib.Path.is_file', return_value=True), patch(
            'pathlib.Path.mkdir'
        ):
            fix_atmosphere.process_atmos(
                'input',
                'output',
                metadata(),
                'model_atmos',
                write_kwargs={'compress': 0, 'dataset_chunks': '8 MiB'},
            )

        self.assertEqual(writes[0][1]['fmt'], 'NETCDF4')
        self.assertEqual(writes[0][1]['single'], True)
        self.assertEqual(writes[0][1]['dataset_chunks'], '8 MiB')
        self.assertEqual(writes[0][1]['compress'], 0)


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