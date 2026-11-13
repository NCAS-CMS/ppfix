from functools import lru_cache
from pathlib import Path

import cf


OROGRAPHY_FILE = Path(__file__).resolve().parent.parent / 'assets' / 'orographies_n1280.nc'


@lru_cache(maxsize=1)
def _read_orographies(orography_file: Path) -> cf.FieldList:
    return cf.read(str(orography_file))


def fix_orography(
    field: cf.Field,
    orography_file: str | Path = OROGRAPHY_FILE,
) -> None:
    """Repair a hybrid-height field's orography in place.

    Existing orography is squeezed to remove singleton axes and stale copied
    coordinates properties are removed. Missing orography
    is read from the bundled N1280 grids (cached across calls). The source file
    is never modified. Raise ValueError if no matching horizontal grid exists.
    """
    cr = field.coordinate_reference(
        'standard_name:atmosphere_hybrid_height_coordinate', default=None
    )
    if cr is None:
        return

    key = cr.coordinate_conversion.domain_ancillaries().get('orog')
    if key is not None:
        orog = field.domain_ancillary(key, default=None)
        if orog is not None:
            axes = tuple(
                axis for axis, size in zip(field.get_data_axes(key), orog.shape)
                if size != 1
            )
            orog = orog.copy()
            orog.squeeze(inplace=True)
            orog.del_property('coordinates', default=None)
            field.set_construct(orog, key=key, axes=axes)
            return

    coordinates = {
        name: field.dimension_coordinate(name, default=None)
        for name in ('latitude', 'longitude')
    }
    for orog in _read_orographies(Path(orography_file)):
        if not all(
            coordinate is not None
            and orog.dimension_coordinate(name).equals(coordinate)
            for name, coordinate in coordinates.items()
        ):
            continue

        axis_map = {
            orog.domain_axis(name, key=True): field.domain_axis(name, key=True)
            for name in coordinates
        }
        axes = tuple(axis_map[axis] for axis in orog.get_data_axes())
        orog_da = cf.DomainAncillary(source=orog)
        orog_da.del_property('coordinates', default=None)
        key = field.set_construct(orog_da, axes=axes)
        cr.coordinate_conversion.set_domain_ancillary('orog', key)
        return

    raise ValueError(
        f'No matching orography grid for {field.identity()!r} in {orography_file}'
    )
