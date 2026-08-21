from __future__ import annotations

import cf
import re


def _pair_to_seconds(start: float, end: float, units_obj: object, units_str: str) -> float | None:
    """Convert two reference-time values to elapsed seconds using cf calendar logic."""
    try:
        dt = cf.Data([start, end], units=units_obj).datetime_array
        td = dt[1] - dt[0]
        return float(td.total_seconds())
    except Exception:
        pass

    # Fallback to unit conversion on the raw interval if datetime decoding fails.
    return _interval_to_seconds(end - start, units_str)


def _interval_to_seconds(delta: float, units: str) -> float | None:
    """Convert a time interval value to seconds from its units string."""
    try:
        return float(cf.Data(delta, units).convert_units("seconds", inplace=False).array)
    except Exception:
        # For reference-time units like "days since 1950-1-1", convert the
        # interval using just the base unit.
        if " since " in units:
            base_units = units.split(" since ", 1)[0].strip()
            try:
                return float(
                    cf.Data(delta, base_units).convert_units("seconds", inplace=False).array
                )
            except Exception:
                pass

    # Final fallback: parse base time-unit text and convert numerically.
    base_units = units.split(" since ", 1)[0].strip().lower()
    # Keep only the first alphabetic token (e.g. "days", "hours").
    match = re.match(r"([a-z]+)", base_units)
    if not match:
        return None

    token = match.group(1)
    unit_seconds = {
        "s": 1.0,
        "sec": 1.0,
        "secs": 1.0,
        "second": 1.0,
        "seconds": 1.0,
        "min": 60.0,
        "mins": 60.0,
        "minute": 60.0,
        "minutes": 60.0,
        "h": 3600.0,
        "hr": 3600.0,
        "hrs": 3600.0,
        "hour": 3600.0,
        "hours": 3600.0,
        "d": 86400.0,
        "day": 86400.0,
        "days": 86400.0,
    }

    factor = unit_seconds.get(token)
    if factor is None:
        return None

    return float(delta) * factor


def inspect_cmip6_temporal_bounds(field: cf.Field) -> dict[str, object]:
    """Inspect temporal coordinates and bounds for cf-python fields.

    Parameters
    ----------
    field:
        A single cf.Field object.

    Returns
    -------
    dict[str, object]
        Result dictionary with coordinate metadata, first bounds, and the
        interval between the first and second time coordinate values.
    """
    identity = field.identity(default="field")
    tcoord = field.dimension_coordinate("T", default=None)

    if tcoord is None:
        tcoord = field.auxiliary_coordinate("T", default=None)

    if tcoord is None:
        return {
            "field_identity": identity,
            "has_time_coordinate": False,
            "message": "No temporal coordinate found on axis T.",
        }

    units_obj = getattr(tcoord, "Units", "")
    units = str(units_obj)
    values = tcoord.array
    n_values = int(values.size)

    bounds = tcoord.get_bounds(default=None) if hasattr(tcoord, "get_bounds") else None
    bounds_array = bounds.array if bounds is not None else None

    first_bounds = None
    if bounds_array is not None and bounds_array.size >= 2:
        first_bounds = [float(bounds_array[0, 0]), float(bounds_array[0, 1])]

    delta_raw = None
    delta_seconds = None
    if n_values >= 2:
        delta_raw = float(values[1] - values[0])
        delta_seconds = _pair_to_seconds(float(values[0]), float(values[1]), units_obj, units)

    return {
        "field_identity": identity,
        "has_time_coordinate": True,
        "time_coordinate_identity": tcoord.identity(default="time"),
        "time_units": units,
        "n_time_values": n_values,
        "first_time_value": float(values[0]) if n_values > 0 else None,
        "second_time_value": float(values[1]) if n_values > 1 else None,
        "interval_first_to_second": delta_raw,
        "interval_first_to_second_units": units,
        "interval_first_to_second_seconds": delta_seconds,
        "has_bounds": bounds_array is not None,
        "first_time_bounds": first_bounds,
        "start_date": tcoord.datetime_array[0] if n_values > 0 else None,
    }


def infer_temporal_frequency(field: cf.Field) -> str:
    """Classify a field into a controlled temporal-frequency vocabulary.

    Returns one of: '1hr', '3hr', '6hr', 'daily', 'monthly', 'fixed'.
    """
    info = inspect_cmip6_temporal_bounds(field)

    if not info.get("has_time_coordinate", False):
        return "fixed"

    seconds = info.get("interval_first_to_second_seconds")
    if seconds is None:
        first_bounds = info.get("first_time_bounds")
        units = info.get("time_units", "")
        units_obj = getattr(
            field.dimension_coordinate("T", default=None)
            or field.auxiliary_coordinate("T", default=None),
            "Units",
            units,
        )
        if isinstance(first_bounds, list) and len(first_bounds) == 2:
            seconds = _pair_to_seconds(first_bounds[0], first_bounds[1], units_obj, units)

    if seconds is None:
        print('===== Unable to infer temporal frequency for field: =====')
        print(info)
        print(field)
        print('==========================================================')
        raise ValueError("Unable to infer temporal frequency from coordinate spacing or bounds.")

    seconds = abs(float(seconds))

    # Allow small tolerance around canonical frequencies.
    canonical = {
        "1hr": 3600.0,
        "3hr": 10800.0,
        "6hr": 21600.0,
        "daily": 86400.0,
    }
    for label, target in canonical.items():
        if abs(seconds - target) <= max(1.0, target * 0.05):
            if 'hr' in label:
                 start_date = info.get("start_date").strftime("%Y%m%d%H")
            else:
                start_date = info.get("start_date").strftime("%Y%m%d")
            return label, start_date

    # Monthly is variable length, so use a broad but still constrained window.
    if 27.0 * 86400.0 <= seconds <= 32.0 * 86400.0:
        start_date = info.get("start_date").strftime("%Y%m")
        return "monthly", start_date

    raise ValueError(
        f"Interval {seconds} s does not match controlled vocabulary "
        "['1hr', '3hr', '6hr', 'daily', 'monthly', 'fixed']."
    )
