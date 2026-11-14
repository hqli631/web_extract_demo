import subprocess
import unittest
from unittest.mock import patch
from learning.check_training_readiness import run_probe,package_versions,readiness

class TrainingReadinessTests(unittest.TestCase):
    def test_probe_error_and_timeout_are_not_no_device(self):
        with patch('learning.check_training_readiness.subprocess.run',return_value=subprocess.CompletedProcess([],1,'','Access denied')):
            result=run_probe(['probe'])
            self.assertEqual(result['status'],'error')
            self.assertNotIn('devices',result)
        with patch('learning.check_training_readiness.subprocess.run',side_effect=subprocess.TimeoutExpired('probe',1)):
            self.assertEqual(run_probe(['probe'])['status'],'unavailable')

    def test_metadata_absence_is_scoped_to_interpreter(self):
        import importlib.metadata
        with patch('learning.check_training_readiness.importlib.metadata.version',side_effect=importlib.metadata.PackageNotFoundError):
            versions=package_versions()
        self.assertEqual(versions['torch']['status'],'not_installed_in_this_interpreter')

    def test_installed_torch_does_not_imply_llm_training_ready(self):
        r=readiness({'torch':{'status':'installed','version':'example'}},{'status':'ok'})
        self.assertEqual(r['llm_training_backend'],'not_verified')
        self.assertFalse(r['actual_llm_training_completed'])
        self.assertEqual(r['reward']['status'],'not_independently_calibrated')
        self.assertEqual(r['model']['status'],'not_selected')

if __name__=='__main__':
    unittest.main()
