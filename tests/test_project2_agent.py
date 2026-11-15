import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class Project2AgentTests(unittest.TestCase):
    def test_task_has_roles_and_frozen_hashes(self):
        task = json.loads((ROOT / 'config/project2_task.json').read_text(encoding='utf8'))
        self.assertEqual({p['role'] for p in task['pages']}, {'generation','development_feedback','final_holdout'})
        self.assertTrue(all(len(p['sha256']) == 64 for p in task['pages']))

    def test_mock_loop_repairs_then_runs_holdout_without_feedback(self):
        proc = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT/'project2_agent.py'), '--provider', 'mock', '--max-rounds', '1', '--output', str(ROOT/'output/project2/test_run')], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        trace = json.loads((ROOT/'output/project2/test_run/trace.json').read_text(encoding='utf8'))
        self.assertEqual(trace['provider'], 'mock')
        self.assertEqual(len(trace['rounds']), 2)
        self.assertEqual(len(trace['holdout']), 1)
        self.assertEqual(trace['api_calls'], 0)
        self.assertFalse(trace['unseen_evaluation'])
        self.assertTrue(trace['holdout'][0]['status'] == 'pass')

    def test_dashscope_fails_closed_without_key(self):
        env = dict(__import__('os').environ)
        env.pop('DASHSCOPE_API_KEY', None)
        proc = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT/'project2_agent.py'), '--provider', 'dashscope', '--max-rounds', '0', '--output', str(ROOT/'output/project2/no_key')], capture_output=True, text=True, env=env)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('DASHSCOPE_API_KEY', proc.stderr + proc.stdout)

if __name__ == '__main__':
    unittest.main()
