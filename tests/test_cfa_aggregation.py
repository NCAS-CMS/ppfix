from pathlib import Path
from time import perf_counter

import cf
import dask
import numpy as np


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
        names = set().union(*(p.keys() for p in properties))
        non_common = sorted(
            name for name in names
            if any(name not in p for p in properties)
            or any(
                type(p[name]) is not type(properties[0][name])
                or not np.array_equal(p[name], properties[0][name])
                for p in properties[1:]
            )
        )
        assert set(PROVENANCE_PROPERTIES) <= set(non_common)
        for name in non_common:
            assert all(name in p for p in properties), (
                f'{name}: missing properties need a masked ancillary representation'
            )
            assert all(np.ndim(p[name]) == 0 for p in properties), (
                f'{name}: this experiment expects scalar source properties'
            )

        aggregated = cf.aggregate(
            fields, axes='T', field_ancillaries=non_common
        )
        assert len(aggregated) == 1
        concatenated = cf.Field.concatenate(fields, axis='T')
        time_axis = concatenated.domain_axis('T', key=True)
        time_sizes = [field.domain_axis('T').size for field in fields]

        for name in non_common:
            values = np.concatenate([
                np.repeat(p[name], size)
                for p, size in zip(properties, time_sizes)
            ])
            ancillary = cf.FieldAncillary(
                properties={'long_name': name}, data=cf.Data(values)
            )
            concatenated.del_property(name, None)
            concatenated.set_construct(ancillary, axes=(time_axis,))

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
