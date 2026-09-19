#!/usr/bin/env python3
"""
simulation_check.py

Walk a directory of aggregated climate-model netCDF output, stat() every file
and write a text manifest of file sizes.  The manifest flags

  * SIZE OUTLIERS - files whose size differs from the median of the "same"
    file in other years by more than a tolerance;
  * MISSING FILES - months for which a file should exist but does not.

Expected filename convention:

    <exp>__<period>__<timestamp>__<cellmethod>__<variable...>.nc
    e.g. hrcm_spinup_udz876__1hr__1950010100__mean__precipitation_flux__z0__pr.nc

where <timestamp> is YYYYMM, YYYYMMDD or YYYYMMDDHH.

Definitions
-----------
  variable : (exp, period, cellmethod, variable-name).  One file per month is
             expected between the first and last month found for the exp.
  series   : normally the same as a variable.  If a variable has *two files
             in the same month* with different timestamp suffixes (DD/DDHH),
             it is split into one series per suffix so they don't collide.
  group    : a series restricted to one calendar month (all the Januaries,
             ...).  Sizes are compared within a group only, so differences in
             month length never trigger a flag.

Missing files
-------------
  1. Gaps: any month between the exp's first and last month with no file for
     a variable/series.  A month covered by a file with a *different* suffix
     (e.g. Jan 1950 named ...0103 instead of ...0100) is not a gap; the suffix
     change is reported as a note instead.
  2. --expected FILE: a list of filenames that should exist (e.g. the file
     names from the source cycle directories).  Anything listed but absent is
     reported.  This is the only way to detect a variable that is missing
     entirely.
"""

import argparse
import os
import re
import statistics
import sys
import textwrap
from collections import Counter, defaultdict, namedtuple
from datetime import datetime

NAME_RE = re.compile(
    r"^(?P<exp>.+?)__(?P<period>[A-Za-z0-9]+)__"
    r"(?P<ts>\d{6}(?:\d{2}){0,2})__"
    r"(?P<method>[A-Za-z0-9]+)__(?P<var>.+)\.nc$"
)

Rec = namedtuple("Rec", "exp period method var year month phase size relpath")

# layout of the text report (columns, 0-based)
IND_RANGE, IND_BLOCK, IND_VAR, IND_LIST = 3, 6, 11, 14
CELL_W = 7          # width of a size string, e.g. "10.1 MB"
MAX_COLS = 80
FLAG_CH = {"LOW": "<", "HIGH": ">", "EMPTY": "!"}
DIFF_SUFFIX_NOTE = "a file exists for this month under a different timestamp suffix"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def human(n, si=False):
    """Human-readable size, at most 7 characters, e.g. '512 B', '10.1 MB'."""
    base = 1000 if si else 1024
    units = ["B", "kB", "MB", "GB", "TB", "PB"] if si else ["B", "KB", "MB", "GB", "TB", "PB"]
    if n < base:
        return f"{n} B"
    v, i = float(n), 0
    while v >= base and i < len(units) - 1:
        v /= base
        i += 1
    s = f"{v:.0f}" if v >= 99.95 else f"{v:.1f}"
    if float(s) >= base and i < len(units) - 1:     # e.g. 1023.9 KB -> 1.0 MB
        v /= base
        i += 1
        s = f"{v:.1f}"
    return f"{s} {units[i]}"


def period_key(p):
    m = re.fullmatch(r"(\d+)hr", p)
    if m:
        return (0, int(m.group(1)), p)
    rank = {"daily": 1, "monthly": 2, "monthlyzm": 3, "seasonal": 4, "annual": 5, "yearly": 5}
    return (rank.get(p, 9), 0, p)


def fmt_ym(ym):
    return f"{ym[0]:04d}{ym[1]:02d}"


def ym_index(ym):
    return ym[0] * 12 + ym[1] - 1


def month_range(first, last):
    y, m = first
    while (y, m) <= last:
        yield (y, m)
        m += 1
        if m > 12:
            y, m = y + 1, 1


def compress_months(months):
    """[(1950,1),(1950,2),(1950,5)] -> '195001-195002, 195005'"""
    runs, start, prev = [], None, None
    for ym in months:
        if start is None:
            start = prev = ym
        elif ym_index(ym) == ym_index(prev) + 1:
            prev = ym
        else:
            runs.append((start, prev))
            start = prev = ym
    if start is not None:
        runs.append((start, prev))
    return ", ".join(fmt_ym(a) if a == b else f"{fmt_ym(a)}-{fmt_ym(b)}" for a, b in runs)


def wrap(text, indent, hang=2):
    return textwrap.wrap(text, width=MAX_COLS, initial_indent=" " * indent,
                         subsequent_indent=" " * (indent + hang))


# --------------------------------------------------------------------------
# scanning
# --------------------------------------------------------------------------
def scan(root, recurse):
    recs, unparsed, errors, ignored = [], [], [], 0

    def onerror(e):
        errors.append((str(getattr(e, "filename", "?")), str(e)))

    for dirpath, dirnames, filenames in os.walk(root, onerror=onerror):
        dirnames.sort()
        if not recurse:
            dirnames[:] = []
        for fn in sorted(filenames):
            if not fn.endswith(".nc"):
                ignored += 1
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, root)
            m = NAME_RE.match(fn)
            if not m:
                unparsed.append(rel)
                continue
            try:
                size = os.stat(path).st_size
            except OSError as e:
                errors.append((path, str(e)))
                continue
            ts = m.group("ts")
            recs.append(Rec(m.group("exp"), m.group("period"), m.group("method"),
                            m.group("var"), int(ts[:4]), int(ts[4:6]), ts[6:],
                            size, rel))
    return recs, unparsed, errors, ignored


def load_expected(path):
    names, bad = [], []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            n = os.path.basename(line)
            (names if NAME_RE.match(n) else bad).append(n)
    return names, bad


# --------------------------------------------------------------------------
# analysis
# --------------------------------------------------------------------------
def analyse(recs, tol, min_group, expected):
    # ---- organise files into variables / series ----------------------------
    by_base = defaultdict(lambda: defaultdict(list))    # base -> ym -> [(phase, size, rel)]
    for r in recs:
        by_base[(r.exp, r.period, r.method, r.var)][(r.year, r.month)].append(
            (r.phase, r.size, r.relpath))

    series = defaultdict(dict)          # skey -> {ym: (size, relpath, phase)}
    dups = []
    for base, months in by_base.items():
        split = any(len({p for p, _, _ in v}) > 1 for v in months.values())
        for ym, items in months.items():
            for phase, size, rel in items:
                skey = base + ((phase if split else None),)
                if ym in series[skey]:
                    dups.append(rel)
                    continue
                series[skey][ym] = (size, rel, phase)

    exp_range = {}
    for skey, d in series.items():
        lo, hi = min(d), max(d)
        cur = exp_range.get(skey[0])
        exp_range[skey[0]] = (min(cur[0], lo), max(cur[1], hi)) if cur else (lo, hi)

    # ---- size outliers -----------------------------------------------------
    groups = defaultdict(list)          # (skey, calendar month) -> [(ym, size)]
    for skey, d in series.items():
        for ym, (size, _, _) in d.items():
            groups[(skey, ym[1])].append((ym, size))

    flags = {}                          # (skey, ym) -> (kind, ratio, median, n)
    assessed = unassessed = 0
    for (skey, _mon), items in groups.items():
        nonzero = [s for _, s in items if s > 0]
        med = statistics.median(nonzero) if len(nonzero) >= min_group else None
        if med is None:
            unassessed += 1
        else:
            assessed += 1
        for ym, s in items:
            if s == 0:
                flags[(skey, ym)] = ("EMPTY", 0.0, med, len(nonzero))
            elif med is not None:
                ratio = s / med
                if ratio < 1 - tol:
                    flags[(skey, ym)] = ("LOW", ratio, med, len(nonzero))
                elif ratio > 1 + tol:
                    flags[(skey, ym)] = ("HIGH", ratio, med, len(nonzero))

    # ---- missing files -----------------------------------------------------
    gaps = {}                           # skey -> [ym]   (drives the '--' cells)
    items = {}                          # (base, ym, phase) -> note ('' = truly missing)
    for skey, d in series.items():
        base, phase = skey[:4], skey[4]
        if phase is None:               # merged series: suffix may vary; use the commonest
            phase = Counter(v[2] for v in d.values()).most_common(1)[0][0]
        first, last = exp_range[skey[0]]
        miss = [ym for ym in month_range(first, last) if ym not in d]
        if miss:
            gaps[skey] = miss
            for ym in miss:
                items[(base, ym, phase)] = ""

    n_expected = n_expected_bad = 0
    if expected is not None:
        exp_names, bad = expected
        n_expected, n_expected_bad = len(exp_names), len(bad)
        present = {os.path.basename(r.relpath) for r in recs}
        for name in exp_names:
            if name in present:
                continue
            m = NAME_RE.match(name)
            ts = m.group("ts")
            base = (m.group("exp"), m.group("period"), m.group("method"), m.group("var"))
            ym, phase = (int(ts[:4]), int(ts[4:6])), ts[6:]
            if by_base.get(base, {}).get(ym):
                items[(base, ym, phase)] = DIFF_SUFFIX_NOTE
            else:
                for k in [k for k in items if k[0] == base and k[1] == ym
                          and k[2] != phase and items[k] == ""]:
                    del items[k]        # same gap already found; keep the exact expected name
                items[(base, ym, phase)] = ""

    return dict(series=series, flags=flags, gaps=gaps, items=items, exp_range=exp_range,
                assessed=assessed, unassessed=unassessed, dups=dups,
                n_expected=n_expected, n_expected_bad=n_expected_bad)


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
def render_grid(dmap, first, last, skey, flags, si):
    """Rows of six calendar months (Jan-Jun / Jul-Dec), labelled with YYYYMM."""
    lines = []
    y, m0 = first[0], (1 if first[1] <= 6 else 7)
    while (y, m0) <= last:
        cells, any_data = [], False
        for m in range(m0, m0 + 6):
            ym = (y, m)
            if ym < first or ym > last:
                cells.append(" " * (CELL_W + 1))
            elif ym in dmap:
                any_data = True
                kind = flags.get((skey, ym), (None,))[0]
                cells.append(f"{human(dmap[ym][0], si):>{CELL_W}}{FLAG_CH.get(kind, ' ')}")
            else:
                cells.append(f"{'--':>{CELL_W}} ")
        if any_data:
            line = " " * IND_LIST + f"{y:04d}{m0:02d} " + " ".join(cells)
            lines.append(line.rstrip())
        y, m0 = (y, 7) if m0 == 1 else (y + 1, 1)
    return lines


def build_manifest(A, only_flagged, si):
    series, flags, gaps, exp_range = A["series"], A["flags"], A["gaps"], A["exp_range"]
    by_exp = defaultdict(list)
    for skey in series:
        by_exp[skey[0]].append(skey)

    out = []
    for exp in sorted(by_exp):
        first, last = exp_range[exp]
        total = len(list(month_range(first, last)))
        out.append(exp)
        out.append(" " * IND_RANGE + f"{fmt_ym(first)} - {fmt_ym(last)}")

        blocks = defaultdict(list)
        for k in by_exp[exp]:
            blocks[(k[1], k[2])].append(k)

        for (period, method) in sorted(blocks, key=lambda b: (period_key(b[0]), b[1])):
            block_lines = []
            for k in sorted(blocks[(period, method)], key=lambda k: (k[3], k[4] or "")):
                var, phase = k[3], k[4]
                dmap = series[k]
                miss = gaps.get(k, [])
                phases = Counter(v[2] for v in dmap.values())
                varies = phase is None and len(phases) > 1
                has_flag = any((k, ym) in flags for ym in dmap)
                if only_flagged and not (has_flag or miss or varies):
                    continue

                name = f"{var}.nc"
                if phase is not None:
                    name += f"   [timestamp suffix after month: {phase or 'none'}]"
                block_lines.append(" " * IND_VAR + name)
                block_lines.extend(render_grid(dmap, first, last, k, flags, si))
                if miss:
                    block_lines.extend(wrap(
                        f"MISSING {len(miss)} of {total}: {compress_months(miss)}", IND_LIST))
                if varies:
                    modal = phases.most_common(1)[0][0]
                    for ph in sorted(phases):
                        if ph != modal:
                            yms = sorted(ym for ym, v in dmap.items() if v[2] == ph)
                            block_lines.extend(wrap(
                                f"note: timestamp suffix is {ph or 'none'} for "
                                f"{compress_months(yms)} ({modal or 'none'} otherwise)",
                                IND_LIST))
            if block_lines:
                out.append(" " * IND_BLOCK + f"__{period}__{method}__")
                out.extend(block_lines)
    return out


def outlier_section(A, si):
    series = A["series"]

    def sort_key(item):
        (skey, ym), _ = item
        return (skey[0], period_key(skey[1]), skey[2], skey[3], skey[4] or "", ym)

    lines = []
    for (skey, ym), (kind, ratio, med, n) in sorted(A["flags"].items(), key=sort_key):
        size, rel, _ = series[skey][ym]
        med_txt = (f"median {human(int(med), si)} (n={n})" if med is not None
                   else "no median (group too small)")
        if kind == "EMPTY":
            head = f"EMPTY  {human(size, si):>8}   {med_txt}"
        else:
            head = f"{kind:<5} {ratio:5.2f}x  {human(size, si):>8}   vs {med_txt}"
        lines.append("  " + head)
        lines.append("      " + rel)
    return lines


def missing_groups(A):
    groups = defaultdict(list)
    for (base, ym, phase), note in A["items"].items():
        groups[(base, phase, note)].append(ym)
    return sorted(groups.items(),
                  key=lambda kv: (kv[0][0][0], period_key(kv[0][0][1]), kv[0][0][2],
                                  kv[0][0][3], kv[0][1], kv[0][2]))


def missing_section(A):
    lines = []
    for (base, phase, note), yms in missing_groups(A):
        exp, period, method, var = base
        lines.append(f"  {exp}__{period}__YYYYMM{phase}__{method}__{var}.nc")
        lines.extend(wrap(f"{len(yms)} missing: {compress_months(sorted(yms))}", 6))
        if note:
            lines.extend(wrap(f"({note})", 6))
    return lines


def missing_names(A):
    names = []
    for (base, ym, phase), note in sorted(A["items"].items()):
        if not note:
            exp, period, method, var = base
            names.append(f"{exp}__{period}__{fmt_ym(ym)}{phase}__{method}__{var}.nc")
    return names


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("root", help="directory containing the aggregated .nc files")
    ap.add_argument("-o", "--output", default="manifest.txt", help="output text file")
    ap.add_argument("-t", "--tolerance", type=float, default=0.25,
                    help="flag files whose size differs from the group median by more "
                         "than this fraction (default 0.25 = +/-25%%)")
    ap.add_argument("-n", "--min-group", type=int, default=3,
                    help="minimum number of files needed in a group (same variable, "
                         "same calendar month) to judge outliers (default 3)")
    ap.add_argument("-e", "--expected", metavar="FILE",
                    help="text file listing filenames that should exist (one per line; "
                         "directories are ignored). Anything listed but absent is reported "
                         "as missing - this is how entirely-missing variables are found")
    ap.add_argument("--missing-list", metavar="FILE",
                    help="also write the full expected filenames of missing files, one per line")
    ap.add_argument("--no-recurse", action="store_true", help="do not descend into subdirectories")
    ap.add_argument("--si", action="store_true", help="use powers of 1000 (kB, MB, GB) instead of 1024")
    ap.add_argument("--only-flagged", action="store_true",
                    help="in the manifest, list only variables with flagged/missing files")
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        sys.exit(f"error: {args.root} is not a directory")

    recs, unparsed, errors, ignored = scan(args.root, not args.no_recurse)
    expected = load_expected(args.expected) if args.expected else None
    A = analyse(recs, args.tolerance, args.min_group, expected)
    body = build_manifest(A, args.only_flagged, args.si)

    kinds = Counter(v[0] for v in A["flags"].values())
    n_missing = sum(1 for note in A["items"].values() if not note)
    n_renamed = len(A["items"]) - n_missing
    n_missing_series = len({(b, ph) for (b, _ym, ph), note in A["items"].items() if not note})

    hdr = [
        "# netCDF file size manifest",
        f"# directory   : {os.path.abspath(args.root)}",
        f"# generated   : {datetime.now().isoformat(timespec='seconds')}",
        f"# files       : {len(recs)} parsed, {len(unparsed)} .nc with unrecognised name, "
        f"{ignored} non-.nc ignored, {len(errors)} stat/walk errors",
        f"# series      : {len(A['series'])}  (exp/period/cell-method/variable[/start-time])",
        f"# MISSING     : {n_missing} files in {n_missing_series} series"
        + (f";  {n_renamed} more expected names absent but month present under another suffix"
           if n_renamed else ""),
    ]
    if expected is not None:
        hdr.append(f"#               (--expected: {A['n_expected']} names checked, "
                   f"{A['n_expected_bad']} unrecognised and skipped)")
    else:
        hdr.append("#               (gaps only; use --expected to also catch wholly-absent variables)")
    hdr += [
        f"# OUTLIERS    : {len(A['flags'])} files  (LOW {kinds['LOW']}, HIGH {kinds['HIGH']}, "
        f"EMPTY {kinds['EMPTY']}); each compared with the median of the same series in the "
        f"same calendar month, flagged if outside +/-{args.tolerance:.0%}",
        f"#               {A['assessed']} groups assessed, {A['unassessed']} groups had fewer "
        f"than {args.min_group} non-empty files (not assessed)",
        "#",
        "# Legend: each row is six calendar months (Jan-Jun or Jul-Dec) starting at the",
        "#         YYYYMM shown.  '--' = no file for that month.  Size markers:",
        "#         '<' much smaller than median   '>' much larger   '!' zero bytes",
        "",
    ]

    out = list(hdr)
    ms = missing_section(A)
    out.append(f"MISSING FILES ({n_missing}"
               + (f" + {n_renamed} with a different suffix" if n_renamed else "") + ")")
    out.extend(ms if ms else ["  none"])
    out.append("")
    fl = outlier_section(A, args.si)
    out.append(f"SIZE OUTLIERS ({len(A['flags'])})")
    out.extend(fl if fl else ["  none"])
    out.append("")
    out.append("MANIFEST")
    out.append("")
    out.extend(body)

    if unparsed:
        out += ["", f"UNRECOGNISED .nc FILENAMES ({len(unparsed)})"] + ["  " + p for p in unparsed]
    if A["dups"]:
        out += ["", f"DUPLICATE (same series+month, ignored) ({len(A['dups'])})"] + \
               ["  " + p for p in A["dups"]]
    if errors:
        out += ["", f"STAT/WALK ERRORS ({len(errors)})"] + [f"  {p}: {e}" for p, e in errors]

    with open(args.output, "w") as fh:
        fh.write("\n".join(out) + "\n")

    if args.missing_list:
        with open(args.missing_list, "w") as fh:
            fh.write("\n".join(missing_names(A)) + ("\n" if n_missing else ""))

    print(f"wrote {args.output}: {len(recs)} files, {len(A['series'])} series; "
          f"{n_missing} MISSING in {n_missing_series} series"
          + (f" (+{n_renamed} with different suffix)" if n_renamed else "")
          + f"; {len(A['flags'])} size outliers "
          f"(LOW {kinds['LOW']}, HIGH {kinds['HIGH']}, EMPTY {kinds['EMPTY']})")


if __name__ == "__main__":
    main()
