import configparser
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ppfix import process_nemo, rechunk_file


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