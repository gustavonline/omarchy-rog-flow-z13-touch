"""Read existing controller; test synthetic inputs without starting it or changing the desktop."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

source = Path(__file__).with_name('control.py')
spec = importlib.util.spec_from_file_location('night', source)
night = importlib.util.module_from_spec(spec)
spec.loader.exec_module(night)
UUID = '00000000-0000-0000-0000-000000000000'


class ExistingPolicyTests(unittest.TestCase):
    def setUp(self):
        self.state = {'manual_blank': False, 'override': None}
        self.config = {'trusted_session': {'enabled': True, 'network_uuid': UUID}}
        self.patches = [patch.object(night, 'AC_POWER'), patch.object(night, 'LID_STATE'),
                        patch.object(night, 'run', return_value=UUID + ':activated'),
                        patch.object(night, 'desktop_session', return_value=('3', False)),
                        patch.object(night.subprocess, 'run', return_value=SimpleNamespace(returncode=0)),
                        patch.object(night, 'running_controller', return_value=night.CONTROLLER_VERSION)]
        self.ac, self.lid, self.run, self.desktop, self.service, self.version = [p.start() for p in self.patches]
        self.ac.read_text.return_value = '1'
        self.lid.read_text.return_value = 'state: closed'

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()

    def candidate(self):
        return night.trusted_candidate(self.state, self.config)

    def test_selected_network_ac_unlocked_closed(self):
        self.assertEqual(self.candidate(), '3')

    def test_battery_does_not_qualify(self):
        self.ac.read_text.return_value = '0'
        self.assertIsNone(self.candidate())

    def test_different_network_does_not_qualify(self):
        self.run.return_value = 'different-profile:activated'
        self.assertIsNone(self.candidate())

    def test_inactive_network_does_not_qualify(self):
        self.run.return_value = UUID + ':activating'
        self.assertIsNone(self.candidate())

    def test_no_unlock_of_locked_session(self):
        self.desktop.return_value = ('3', True)
        self.assertIsNone(self.candidate())

    def test_unknown_lock_state_fails(self):
        self.desktop.side_effect = RuntimeError('Unknown native lock state')
        with self.assertRaises(RuntimeError):
            self.candidate()

    def test_manual_blank_is_preserved(self):
        self.state['manual_blank'] = True
        self.assertIsNone(self.candidate())

    def test_explicit_night_override_is_preserved(self):
        self.state['override'] = {'until': night.time.time() + 300, 'on': True}
        self.assertIsNone(self.candidate())

    def test_open_lid_is_not_continuous_trusted_mode(self):
        self.lid.read_text.return_value = 'state: open'
        self.assertIsNone(self.candidate())
        self.assertEqual(night.trusted_candidate(self.state, self.config, require_closed=False), '3')

    def test_unknown_lid_fails(self):
        self.lid.read_text.return_value = 'unknown'
        with self.assertRaises(RuntimeError):
            self.candidate()

    def test_dead_or_stale_controller_fails(self):
        self.service.return_value.returncode = 3
        with self.assertRaises(RuntimeError):
            self.candidate()
        self.service.return_value.returncode = 0
        self.version.return_value = 'old'
        with self.assertRaises(RuntimeError):
            self.candidate()


if __name__ == '__main__':
    unittest.main(verbosity=2)
