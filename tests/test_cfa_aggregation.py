from pathlib import Path
from time import perf_counter

import cf
import dask
import numpy as np
import pytest

from ppfix import concatenate_with_ancillaries


DATA_DIR = Path(__file__).parent / 'data' / 'cfa' / 'monthlyzm_air_temperature_p36'
PROVENANCE_PROPERTIES = ('original_output', 'tracking_id', 'start_date')


def test_example_field_concatenation_matches_aggregation():
    expected = cf.example_field(2)[:24]
    fields = [expected[:7], expected[7:19], expected[19:]]

    with dask.config.set(scheduler='synchronous'):
        aggregated = cf.aggregate(fields)
        concatenated = cf.Field.concatenate(fields, axis='T')

        assert len(aggregated) == 1
        assert expected.equals(aggregated[0], rtol=0, atol=0, verbose=2)
        assert expected.equals(concatenated, rtol=0, atol=0, verbose=2)


def test_real_file_concatenation_matches_aggregation_except_provenance(
    record_property,
):
    paths = sorted(DATA_DIR.glob(
        '*__monthlyzm__*__mean__air_temperature__p36__*.nc'
    ))
    assert len(paths) == 24, f'Expected 24 bundled input files in {DATA_DIR}'

    with dask.config.set(scheduler='synchronous'):
        start = perf_counter()
        aggregated = cf.read([str(path) for path in paths])
        aggregate_seconds = perf_counter() - start
        assert len(aggregated) == 1

        start = perf_counter()
        fields = []
        for path in paths:
            result = cf.read(str(path), aggregate=False)
            assert len(result) == 1, f'Expected one field in {path}'
            fields.append(result[0])
        read_seconds = perf_counter() - start

        start = perf_counter()
        concatenated = cf.Field.concatenate(fields, axis='T')
        concatenate_seconds = perf_counter() - start

        assert concatenated.shape == (24, 36, 1921, 1)
        assert concatenated.dtype == np.dtype('float32')
        time = concatenated.dimension_coordinate('T')
        dates = time.datetime_array
        assert (dates[0].year, dates[0].month) == (1950, 1)
        assert (dates[-1].year, dates[-1].month) == (1951, 12)
        assert np.all(np.diff(time.array) > 0)

        aggregate_properties = aggregated[0].properties()
        concatenate_properties = concatenated.properties()
        assert aggregate_properties.keys() == concatenate_properties.keys()
        differences = {
            key for key in aggregate_properties
            if type(aggregate_properties[key]) is not type(concatenate_properties[key])
            or not np.array_equal(
                aggregate_properties[key], concatenate_properties[key]
            )
        }
        assert differences == set(PROVENANCE_PROPERTIES)

        # This diagnoses current behaviour, not the required ancillary preservation.
        assert aggregated[0].equals(
            concatenated,
            ignore_properties=PROVENANCE_PROPERTIES,
            rtol=0,
            atol=0,
            verbose=2,
        )

    record_property('aggregation_seconds', aggregate_seconds)
    record_property('individual_read_seconds', read_seconds)
    record_property('concatenation_seconds', concatenate_seconds)
    record_property('cf_python_version', cf.__version__)
    print(
        f'Aggregation: {aggregate_seconds:.3f}s; '
        f'individual reads: {read_seconds:.3f}s; '
        f'concatenation: {concatenate_seconds:.3f}s; '
        f'reads + concatenation: {read_seconds + concatenate_seconds:.3f}s; '
        f'differing properties: {sorted(differences)}'
    )


def test_real_file_concatenation_with_ancillaries_fully_matches_aggregation():
    paths = sorted(DATA_DIR.glob(
        '*__monthlyzm__*__mean__air_temperature__p36__*.nc'
    ))
    assert len(paths) == 24, f'Expected 24 bundled input files in {DATA_DIR}'

    with dask.config.set(scheduler='synchronous'):
        fields = []
        for path in paths:
            result = cf.read(str(path), aggregate=False)
            assert len(result) == 1, f'Expected one field in {path}'
            fields.append(result[0])

        properties = [field.properties() for field in fields]
        non_common = PROVENANCE_PROPERTIES
        aggregated = cf.aggregate(
            fields, axes='T', field_ancillaries=non_common
        )
        assert len(aggregated) == 1
        concatenated = concatenate_with_ancillaries(fields)
        time_sizes = [field.domain_axis('T').size for field in fields]

        for output in (aggregated[0], concatenated):
            output_time_axis = output.domain_axis('T', key=True)
            ancillaries = {
                ancillary.get_property('long_name'): (key, ancillary)
                for key, ancillary in output.field_ancillaries(todict=True).items()
            }
            assert set(ancillaries) == set(non_common)
            for name in non_common:
                assert not output.has_property(name)
                key, ancillary = ancillaries[name]
                assert output.get_data_axes(key) == (output_time_axis,)
                assert ancillary.shape == (sum(time_sizes),)
                offset = 0
                for p, size in zip(properties, time_sizes):
                    np.testing.assert_array_equal(
                        ancillary.array[offset:offset + size],
                        np.full(size, p[name]),
                    )
                    offset += size

        assert aggregated[0].equals(
            concatenated, rtol=0, atol=0, verbose=2
        )


@pytest.mark.parametrize('with_provenance', [False, True])
def test_public_concatenation_matches_reference_without_changing_inputs(
    with_provenance,
):
    expected = cf.example_field(2)[:24]
    expected.set_property('experiment', 'concatenation-test')
    fields = [expected[:7], expected[7:19], expected[19:]]
    non_common = ('source_note', 'processing_index') if with_provenance else ()
    if with_provenance:
        for index, (field, note) in enumerate(zip(
            fields, ('first', 'a longer source note', 'last')
        )):
            field.set_property('source_note', note)
            field.set_property('processing_index', np.int32(index))
    originals = [field.copy() for field in fields]

    with dask.config.set(scheduler='synchronous'):
        aggregated = cf.aggregate(
            fields, axes='T', field_ancillaries=non_common
        )
        result = concatenate_with_ancillaries(fields, axis='time')

        assert len(aggregated) == 1
        assert aggregated[0].equals(result, rtol=0, atol=0, verbose=2)
        if not with_provenance:
            assert expected.equals(result, rtol=0, atol=0, verbose=2)
        for field, original in zip(fields, originals):
            assert original.equals(field, rtol=0, atol=0, verbose=2)


def test_public_concatenation_rejects_empty_input():
    with pytest.raises(ValueError, match='At least one field'):
        concatenate_with_ancillaries([])


@pytest.mark.parametrize('invalid_property', ['missing', 'non-scalar'])
def test_public_concatenation_rejects_unsupported_properties(invalid_property):
    example = cf.example_field(2)
    fields = [example[:1], example[1:2]]
    if invalid_property == 'missing':
        fields[0].set_property('source_note', 'first')
        message = "'source_note'.*missing"
    else:
        fields[0].set_property('source_note', ['first', 'second'])
        fields[1].set_property('source_note', ['third', 'fourth'])
        message = "'source_note'.*scalar"

    with pytest.raises(ValueError, match=message):
        concatenate_with_ancillaries(fields)
