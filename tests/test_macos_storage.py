from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from game_storage import SaveStore, default_storage_root


class MacStorageTests(unittest.TestCase):
    def test_frozen_mac_uses_user_library_even_when_resources_are_read_only(self):
        with patch.object(sys, 'platform', 'darwin'), patch.object(sys, 'frozen', True, create=True), \
             patch('game_storage.Path.home', return_value=Path('/users/test-player')):
            store = SaveStore()
            self.assertEqual(store.root, Path('/users/test-player/Library/Application Support/Second Presence'))
            self.assertEqual(store.path.name, 'save.json')
            self.assertEqual(store.settings_path.name, 'settings.json')

    def test_source_launch_preserves_existing_local_saves(self):
        with patch.object(sys, 'frozen', False, create=True):
            self.assertEqual(default_storage_root().name, '.user_data')

    def test_explicit_storage_remains_available_for_isolated_checks(self):
        with patch.object(sys, 'platform', 'darwin'), patch.object(sys, 'frozen', True, create=True):
            self.assertEqual(SaveStore('/tmp/separate-test-slot').root, Path('/tmp/separate-test-slot'))
