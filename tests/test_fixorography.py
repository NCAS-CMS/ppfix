from pathlib import Path
import re
from unittest.mock import patch

import cf
from netCDF4 import Dataset
import pytest

from ppfix import fixorography


@pytest.fixture(autouse=True)
def clear_orography_cache():
    fixorography._read_orographies.cache_clear()
    yield
    fixorography._read_orographies.cache_clear()


def hybrid_field(orography):
    field = orography.copy()
    field.set_property('standard_name', 'air_temperature')
    field.set_construct(cf.CoordinateReference(
        coordinate_conversion=cf.CoordinateConversion(
            parameters={'standard_name': 'atmosphere_hybrid_height_coordinate'}
        )
    ))
    return field


def vertical_reference(field):
    return field.coordinate_reference(
        'standard_name:atmosphere_hybrid_height_coordinate'
    )


def test_non_hybrid_field_does_not_read_orography():
    field = cf.example_field(0)
    original = field.copy()
    with patch.object(fixorography.cf, 'read') as read:
        fixorography.fix_orography(field)
    read.assert_not_called()
    assert field.equals(original)


def test_existing_orography_is_squeezed_without_reading_asset():
    field = cf.example_field(1)
    cr = vertical_reference(field)
    key = cr.coordinate_conversion.domain_ancillaries()['orog']
    axes = field.get_data_axes(key)
    original = field.domain_ancillary(key).copy()
    expanded = original.insert_dimension(position=0)
    time_axis = field.domain_axis('T', key=True)
    field.set_construct(expanded, key=key, axes=(time_axis, *axes))

    with patch.object(fixorography.cf, 'read') as read:
        fixorography.fix_orography(field)

    read.assert_not_called()
    assert cr.coordinate_conversion.domain_ancillaries()['orog'] == key
    assert field.get_data_axes(key) == axes
    assert field.domain_ancillary(key).equals(original)


def test_written_coordinate_references_resolve(tmp_path):
    field = cf.example_field(1)
    key = vertical_reference(field).coordinate_conversion.domain_ancillaries()['orog']
    original = field.domain_ancillary(key)
    original.set_property('coordinates', 'latitude_99 longitude_99')
    stale_properties = original.properties()

    fixorography.fix_orography(field)

    assert original.properties() == stale_properties
    assert not field.domain_ancillary(key).has_property('coordinates')
    output = tmp_path / 'repaired_orography.nc'
    cf.write(field, str(output), overwrite=False)

    with Dataset(output, mode='r') as dataset:
        references = {'coordinates': 0, 'formula_terms': 0}
        for variable in dataset.variables.values():
            for attribute in references:
                if attribute not in variable.ncattrs():
                    continue
                references[attribute] += 1
                value = variable.getncattr(attribute)
                names = (
                    value.split() if attribute == 'coordinates'
                    else re.findall(r'\S+:\s*(\S+)', value)
                )
                assert names, (variable.name, attribute, value)
                for name in names:
                    assert name in dataset.variables, (variable.name, attribute, name)
        assert all(references.values())
        assert 'orog:' in dataset.variables[
            field.dimension_coordinate('atmosphere_hybrid_height_coordinate').nc_get_variable()
        ].getncattr('formula_terms')


@pytest.mark.parametrize('transpose', [False, True])
def test_matching_grid_is_inserted_with_explicit_axes_and_cached(tmp_path, transpose):
    # Equal-sized axes make shape-based axis inference ambiguous.
    orography = cf.example_field(0)[:, :5]
    orography.set_property('standard_name', 'surface_altitude')
    orography.override_units('m', inplace=True)
    if transpose:
        orography.transpose(inplace=True)
    orography.set_property('coordinates', 'latitude_99 longitude_99')
    original = orography.copy()
    wrong_grid = orography.copy()
    wrong_grid.dimension_coordinate('longitude').set_data(
        orography.dimension_coordinate('longitude').data + 1
    )
    fields = [hybrid_field(orography), hybrid_field(orography)]
    source = tmp_path / 'orography.nc'

    with patch.object(
        fixorography.cf, 'read', return_value=cf.FieldList([wrong_grid, orography])
    ) as read:
        for field in fields:
            fixorography.fix_orography(field, orography_file=source)
            key = vertical_reference(field).coordinate_conversion.domain_ancillaries()['orog']
            assert field.get_data_axes(key) == tuple(
                field.domain_axis(orography.dimension_coordinate(
                    filter_by_axis=(axis,)
                ).identity(), key=True)
                for axis in orography.get_data_axes()
            )
            assert field.domain_ancillary(key).data.equals(orography.data)
            assert not field.domain_ancillary(key).has_property('coordinates')
            fixorography.fix_orography(field, orography_file=source)
            assert len(field.domain_ancillaries()) == 1

    read.assert_called_once_with(str(source))
    assert orography.equals(original)


def test_unmatched_grid_raises():
    orography = cf.example_field(0)
    field = hybrid_field(orography)
    orography.dimension_coordinate('latitude').set_data(
        orography.dimension_coordinate('latitude').data + 1
    )

    with patch.object(fixorography.cf, 'read', return_value=[orography]):
        with pytest.raises(ValueError, match='No matching orography grid'):
            fixorography.fix_orography(field)

    assert not field.domain_ancillaries()


def test_missing_asset_error_is_not_suppressed():
    field = hybrid_field(cf.example_field(0))
    with patch.object(fixorography.cf, 'read', side_effect=FileNotFoundError):
        with pytest.raises(FileNotFoundError):
            fixorography.fix_orography(field, orography_file='missing.nc')


def test_default_asset_is_relative_to_module():
    assert fixorography.OROGRAPHY_FILE == (
        Path(fixorography.__file__).resolve().parent.parent
        / 'assets' / 'orographies_n1280.nc'
    )


def test_bundled_grids_match_without_modifying_sources():
    orographies = cf.read(str(fixorography.OROGRAPHY_FILE))
    for orography in orographies:
        field = hybrid_field(orography)
        fixorography.fix_orography(field)
        key = vertical_reference(field).coordinate_conversion.domain_ancillaries()['orog']
        ancillary = field.domain_ancillary(key)
        assert ancillary.shape == orography.shape
        assert ancillary.get_property('standard_name') == 'surface_altitude'
        assert field.get_data_axes(key) == field.get_data_axes()
