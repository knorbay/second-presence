"""Installed builds must save in writable per-user folders, not the bundle."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from game_storage import default_storage_root


class DesktopStorageTests(unittest.TestCase):
    def test_windows_local_app_data(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'platform', 'win32'), patch.dict(os.environ, {'LOCALAPPDATA': str(Path.home()/'test-local')}):
            self.assertEqual(default_storage_root(), Path.home()/'test-local'/'Second Presence')

    def test_linux_uses_xdg_state(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'platform', 'linux'), patch.dict(os.environ, {'XDG_STATE_HOME': str(Path.home()/'test-state')}):
            self.assertEqual(default_storage_root(), Path.home()/'test-state'/'second-presence')

    def test_linux_rejects_relative_xdg_path(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'platform', 'linux'), patch.dict(os.environ, {'XDG_STATE_HOME': 'relative'}):
            self.assertEqual(default_storage_root(), Path.home()/'.local'/'state'/'second-presence')

    def test_windows_default_when_environment_missing(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'platform', 'win32'), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(default_storage_root(), Path.home()/'AppData'/'Local'/'Second Presence')
