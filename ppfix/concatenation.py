from collections.abc import Sequence

import cf
import numpy as np


def concatenate_with_ancillaries(
    fields: Sequence[cf.Field], axis: str = 'T'
) -> cf.Field:
    """Concatenate already-read fields, preserving differing scalar properties.

    Common properties remain field properties. Non-common properties become
    field ancillaries spanning ``axis``, with each source value repeated over
    that source's axis length. Inputs are not modified and no files are read
    or written.

    Fields must already be ordered along the concatenation axis and compatible
    with ``cf.Field.concatenate``. Raise ValueError for empty input or for
    non-common properties that are missing from an input or are not scalar.
    """
    if not fields:
        raise ValueError('At least one field is required for concatenation')

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
    for name in non_common:
        if any(name not in p for p in properties):
            raise ValueError(
                f'Non-common property {name!r} is missing from one or more fields'
            )
        if any(np.ndim(p[name]) != 0 for p in properties):
            raise ValueError(
                f'Non-common property {name!r} must be scalar in every field'
            )

    concatenated = cf.Field.concatenate(fields, axis=axis, copy=True)
    if non_common:
        axis_key = concatenated.domain_axis(axis, key=True)
        sizes = [field.domain_axis(axis).size for field in fields]
        for name in non_common:
            values = np.concatenate([
                np.repeat(p[name], size)
                for p, size in zip(properties, sizes)
            ])
            ancillary = cf.FieldAncillary(
                properties={'long_name': name}, data=cf.Data(values)
            )
            concatenated.del_property(name)
            concatenated.set_construct(ancillary, axes=(axis_key,))

    return concatenated
