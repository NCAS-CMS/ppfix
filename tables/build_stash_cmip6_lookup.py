#!/usr/bin/env python3
"""
Parse the Met Office CDDS (mip_convert) HadGEM3 'model to MIP mapping' .cfg
files and build a STASH -> CMIP6 short-name lookup table.

Source: https://github.com/MetOffice/CDDS
        mip_convert/mip_convert/plugins/hadgem3/data/*.cfg

Each .cfg file is an INI-style file. Each section (other than [DEFAULT] and
[COMMON]) is one CMIP6 (or CMIP6Plus/other project) variable, keyed by its
short name (e.g. "tas"). Key fields used here:

    mip_table_id : space-separated list of MIP table(s) this mapping is used
                   for (e.g. "Amon", or "AERmon AEmon" if shared).
    expression   : a formula referencing one or more STASH codes, each
                   optionally followed by a bracketed qualifier list, e.g.
                       m01s03i236[lbproc=0]
                       m01s30i296[blev=PLEV19, lbproc=128]
                       m01s02i530[lbplev=3, lbproc=0]

A STASH reference is: m01s<SS>i<III>  (section SS, item III), followed
optionally by a long-name description text and/or a bracketed qualifier
block.

Output: two CSV/JSON lookup tables --
  1. stash_cmip6_simple  - one row per (stash, mip_table, short_name) where
     the expression is built from EXACTLY ONE stash reference (a direct /
     near-direct mapping). This is the table to match your own
     stash+lbproc+lbplev combinations against.
  2. stash_cmip6_all     - one row per stash reference found in ANY
     expression (including multi-stash / combined diagnostics), for
     reference/debugging, with a flag marking whether it came from a
     "simple" (single-stash) or "combined" (multi-stash) expression.
"""

import configparser
import csv
import json
import re
from pathlib import Path

DATA_DIR = Path(
    "/home/claude/cdds_repo/mip_convert/mip_convert/plugins/hadgem3/data"
)
OUT_DIR = Path("/home/claude/out")
OUT_DIR.mkdir(exist_ok=True)

# Matches a STASH reference like m01s03i236, optionally followed by a
# run of description text (letters/digits/spaces/punctuation, no '[' '('),
# optionally followed by a bracketed qualifier block [key=val, key=val].
STASH_RE = re.compile(
    r"""
    (?P<stash>m01s\d{2}i\d{3})              # the stash code itself
    (?P<longname>[^\[\](),+\-*/]*)          # optional trailing description text
    (?:\[(?P<quals>[^\]]*)\])?              # optional [qualifiers]
    """,
    re.VERBOSE,
)

QUAL_RE = re.compile(r"(\w+)\s*=\s*([^,]+)")


def parse_qualifiers(qual_str):
    """Turn 'blev=PLEV19, lbproc=128' into {'blev': 'PLEV19', 'lbproc': '128'}."""
    if not qual_str:
        return {}
    return {k: v.strip() for k, v in QUAL_RE.findall(qual_str)}


def stash_to_section_item(stash):
    """m01s03i236 -> (3, 236)"""
    m = re.match(r"m01s(\d{2})i(\d{3})", stash)
    section, item = int(m.group(1)), int(m.group(2))
    return section, item


def find_stash_refs(expression):
    """Return list of dicts: stash, section, item, longname, qualifiers."""
    refs = []
    for m in STASH_RE.finditer(expression):
        stash = m.group("stash")
        section, item = stash_to_section_item(stash)
        longname = (m.group("longname") or "").strip()
        quals = parse_qualifiers(m.group("quals"))
        refs.append(
            {
                "stash": stash,
                "section": section,
                "item": item,
                "long_name_text": longname,
                "qualifiers": quals,
            }
        )
    return refs


def load_all_mappings():
    rows = []
    cfg_files = sorted(DATA_DIR.glob("HadGEM3*mappings.cfg"))
    for cfg_path in cfg_files:
        parser = configparser.ConfigParser(strict=False, interpolation=None)
        # Preserve case of variable (section) names
        parser.optionxform = str
        try:
            parser.read(cfg_path, encoding="utf-8")
        except configparser.Error as e:
            print(f"WARNING: failed to parse {cfg_path.name}: {e}")
            continue

        for section in parser.sections():
            if section == "COMMON":
                continue
            short_name = section
            data = parser[section]
            expression = data.get("expression", "")
            mip_tables_raw = data.get("mip_table_id", "")
            mip_tables = mip_tables_raw.split()
            units = data.get("units", "")
            component = data.get("component", "")
            status = data.get("status", "")
            comment = data.get("comment", "")

            stash_refs = find_stash_refs(expression)
            is_simple = len(stash_refs) == 1

            for mip_table in mip_tables or [""]:
                rows.append(
                    {
                        "cmip6_short_name": short_name,
                        "mip_table": mip_table,
                        "n_stash_refs": len(stash_refs),
                        "is_simple": is_simple,
                        "units": units,
                        "component": component,
                        "status": status,
                        "comment": comment,
                        "expression": expression.strip(),
                        "source_file": cfg_path.name,
                        "stash_refs": stash_refs,
                    }
                )
    return rows


def build_lookup_tables(rows):
    simple_rows = []
    all_stash_rows = []

    for row in rows:
        for ref in row["stash_refs"]:
            all_stash_rows.append(
                {
                    "stash": ref["stash"],
                    "stash_section": ref["section"],
                    "stash_item": ref["item"],
                    "lbproc": ref["qualifiers"].get("lbproc", ""),
                    "lblev": ref["qualifiers"].get("lblev", ""),
                    "lbplev": ref["qualifiers"].get("lbplev", ""),
                    "blev": ref["qualifiers"].get("blev", ""),
                    "cmip6_short_name": row["cmip6_short_name"],
                    "mip_table": row["mip_table"],
                    "is_simple_mapping": row["is_simple"],
                    "n_stash_refs_in_expression": row["n_stash_refs"],
                    "units": row["units"],
                    "status": row["status"],
                    "expression": row["expression"],
                    "source_file": row["source_file"],
                }
            )
            if row["is_simple"]:
                simple_rows.append(all_stash_rows[-1])

    return simple_rows, all_stash_rows


def main():
    rows = load_all_mappings()
    print(f"Parsed {len(rows)} (variable, mip_table) mapping rows "
          f"from {len(list(DATA_DIR.glob('HadGEM3*mappings.cfg')))} cfg files")

    simple_rows, all_stash_rows = build_lookup_tables(rows)
    print(f"  -> {len(simple_rows)} simple (single-STASH) mapping rows")
    print(f"  -> {len(all_stash_rows)} total STASH-reference rows (incl. combined diagnostics)")

    fieldnames = [
        "stash", "stash_section", "stash_item",
        "lbproc", "lblev", "lbplev", "blev",
        "cmip6_short_name", "mip_table",
        "is_simple_mapping", "n_stash_refs_in_expression",
        "units", "status", "expression", "source_file",
    ]

    with open(OUT_DIR / "stash_cmip6_simple.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(simple_rows)

    with open(OUT_DIR / "stash_cmip6_all.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_stash_rows)

    with open(OUT_DIR / "stash_cmip6_simple.json", "w") as f:
        json.dump(simple_rows, f, indent=2)

    with open(OUT_DIR / "stash_cmip6_all.json", "w") as f:
        json.dump(all_stash_rows, f, indent=2)

    print("Wrote stash_cmip6_simple.{csv,json} and stash_cmip6_all.{csv,json} to", OUT_DIR)


if __name__ == "__main__":
    main()
