from __future__ import annotations

import csv
import re
from pathlib import Path


FAILED_TASK_RE = re.compile(r'(?P<prefix>.+)_(?P<job_id>\d+)_(?P<task_id>\d+)\.err$')


def load_manifest(manifest_file: Path) -> list[str]:
    return [line.strip() for line in manifest_file.read_text().splitlines() if line.strip()]


def first_nonempty_line(path: Path) -> str:
    for line in path.read_text(errors='replace').splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ''


def collect_failed_tasks(slurm_output_dir: Path, manifest_file: Path) -> list[dict[str, str]]:
    manifest_entries = load_manifest(manifest_file)
    failures = []

    for err_file in sorted(slurm_output_dir.glob('*.err')):
        match = FAILED_TASK_RE.match(err_file.name)
        if match is None or err_file.stat().st_size == 0:
            continue

        task_id = int(match.group('task_id'))
        input_file = ''
        if 0 <= task_id < len(manifest_entries):
            input_file = manifest_entries[task_id]

        failures.append(
            {
                'job_id': match.group('job_id'),
                'task_id': match.group('task_id'),
                'input_file': input_file,
                'error_file': str(err_file.resolve()),
                'output_file': str(err_file.with_suffix('.out').resolve()),
                'error_summary': first_nonempty_line(err_file),
            }
        )

    return failures


def write_failure_reports(
    failures: list[dict[str, str]],
    report_file: Path,
    failed_manifest_file: Path,
) -> None:
    report_file.parent.mkdir(parents=True, exist_ok=True)
    failed_manifest_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ['job_id', 'task_id', 'input_file', 'error_file', 'output_file', 'error_summary']
    with report_file.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(failures)

    failed_inputs = [failure['input_file'] for failure in failures if failure['input_file']]
    failed_manifest_file.write_text('\n'.join(failed_inputs) + ('\n' if failed_inputs else ''))