import argparse
from pathlib import Path

from ppfix.slurm_failures import collect_failed_tasks, write_failure_reports


def parse_args():
    parser = argparse.ArgumentParser(
        description='Parse Slurm array error files and map failed tasks back to manifest inputs.'
    )
    parser.add_argument('slurm_output_directory', type=Path)
    parser.add_argument('manifest_file', type=Path)
    parser.add_argument('--report-file', type=Path)
    parser.add_argument('--failed-manifest-file', type=Path)
    return parser.parse_args()


def main():
    args = parse_args()

    slurm_output_directory = args.slurm_output_directory.expanduser().resolve()
    manifest_file = args.manifest_file.expanduser().resolve()

    report_file = args.report_file
    if report_file is None:
        report_file = slurm_output_directory / 'failed-tasks.csv'
    else:
        report_file = report_file.expanduser().resolve()

    failed_manifest_file = args.failed_manifest_file
    if failed_manifest_file is None:
        failed_manifest_file = slurm_output_directory / 'failed-file-manifest.txt'
    else:
        failed_manifest_file = failed_manifest_file.expanduser().resolve()

    failures = collect_failed_tasks(slurm_output_directory, manifest_file)
    write_failure_reports(failures, report_file, failed_manifest_file)

    print(f'Found {len(failures)} failed tasks.')
    print(f'Failure report written to {report_file}')
    print(f'Failed manifest written to {failed_manifest_file}')


if __name__ == '__main__':
    main()