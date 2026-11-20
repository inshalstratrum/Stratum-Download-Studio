
import unittest
from pathlib import Path
import tempfile
import shutil
import os
import sys
sys.path.append(str(Path(__file__).parent.parent))
from stratum_download_studio import collect_output_candidates

class TestOutputDiscovery(unittest.TestCase):
    def test_collect_output_candidates_ignores_other_jobs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            save_dir = Path(tmpdir)
            # Create a file that existed before
            preexisting = save_dir / "old.mp4"
            preexisting.touch()

            # Create a newer file that should be ignored if it doesn't belong to this job
            # The issue is that collect_output_candidates globbing all *.mp4 files
            other_job_file = save_dir / "other_job.mp4"
            other_job_file.touch()

            # Simulate a job that only produced "new.mp4"
            new_file = save_dir / "new-job.mp4"
            new_file.touch()

            candidates = collect_output_candidates(
                info={},
                postprocessed_paths=[str(new_file)],
                save_dir=str(save_dir),
                extension="mp4",
                output_tag="-job",
                preexisting=[str(preexisting)]
            )

            self.assertIn(str(new_file), candidates)
            self.assertNotIn(str(other_job_file), candidates, "Should not include files not associated with the job")

if __name__ == '__main__':
    unittest.main()
