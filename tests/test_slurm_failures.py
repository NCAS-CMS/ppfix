from pathlib import Path
import tempfile
import unittest

from ppfix.slurm_failures import collect_failed_tasks, write_failure_reports


class SlurmFailureTests(unittest.TestCase):
    def test_collects_nonempty_error_files_and_maps_manifest_entries(self):
        with tempfile.TemporaryDirectory() as tempdir:
            tempdir = Path(tempdir)
            slurm_dir = tempdir / 'slurm-out'
            slurm_dir.mkdir()
            manifest_file = tempdir / 'file-manifest.txt'
            manifest_file.write_text('/data/input0\n/data/input1\n/data/input2\n')

            (slurm_dir / 'ppfix_4000_0.err').write_text('')
            (slurm_dir / 'ppfix_4000_1.err').write_text('Traceback: bad file\nmore detail\n')
            (slurm_dir / 'ppfix_4000_2.err').write_text('OOM killed\n')

            failures = collect_failed_tasks(slurm_dir, manifest_file)

            self.assertEqual([failure['task_id'] for failure in failures], ['1', '2'])
            self.assertEqual(failures[0]['input_file'], '/data/input1')
            self.assertEqual(failures[1]['input_file'], '/data/input2')
            self.assertEqual(failures[0]['error_summary'], 'Traceback: bad file')

            report_file = tempdir / 'failed-tasks.csv'
            failed_manifest = tempdir / 'failed-file-manifest.txt'
            write_failure_reports(failures, report_file, failed_manifest)

            self.assertIn('job_id,task_id,input_file,error_file,output_file,error_summary', report_file.read_text())
            self.assertEqual(failed_manifest.read_text(), '/data/input1\n/data/input2\n')


if __name__ == '__main__':
    unittest.main()