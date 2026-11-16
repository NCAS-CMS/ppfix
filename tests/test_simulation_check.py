from ppfix.simulation_check import (
    DIFF_SUFFIX_NOTE,
    Rec,
    analyse,
    missing_names,
    missing_section,
)


def test_suffix_swap_in_month_is_not_counted_missing():
    recs = [
        Rec(
            exp="hrcm_spinup_udz876",
            period="1hr",
            method="point",
            var="toa_outgoing_longwave_flux__z0__",
            year=1950,
            month=1,
            phase="0101",
            size=100,
            relpath="jan_0101.nc",
        ),
        Rec(
            exp="hrcm_spinup_udz876",
            period="1hr",
            method="point",
            var="toa_outgoing_longwave_flux__z0__",
            year=1950,
            month=2,
            phase="0100",
            size=100,
            relpath="feb_0100.nc",
        ),
        Rec(
            exp="hrcm_spinup_udz876",
            period="1hr",
            method="point",
            var="toa_outgoing_longwave_flux__z0__",
            year=1950,
            month=2,
            phase="0101",
            size=100,
            relpath="feb_0101.nc",
        ),
    ]

    analysed = analyse(recs, tol=0.25, min_group=3, expected=None)

    # No true missing files should be reported for this case.
    assert all(note for note in analysed["items"].values())
    assert list(analysed["items"].values()) == [DIFF_SUFFIX_NOTE]
    assert analysed["gaps"] == {}


def test_expected_missing_suffixes_are_all_reported():
    recs = [
        Rec("run", "1hr", "mean", "temperature", 1950, month, "0102", 100, f"{month}.nc")
        for month in (1, 3)
    ]
    names = [
        f"run__1hr__195002{phase}__mean__temperature.nc"
        for phase in ("0100", "0101")
    ]

    for records in (recs, []):
        for expected in (names, list(reversed(names))):
            analysed = analyse(records, tol=0.25, min_group=3, expected=(expected, []))
            assert missing_names(analysed) == names
            report = "\n".join(missing_section(analysed))
            assert "YYYYMM0100" in report
            assert "YYYYMM0101" in report
            assert "YYYYMM0102" not in report
