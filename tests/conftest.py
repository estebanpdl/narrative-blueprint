"""Activate offline protections before importing application tests."""

import pytest

from offline_guard import install_guard


_offline_patch = pytest.MonkeyPatch()
install_guard(_offline_patch)


def pytest_unconfigure(config):
    _offline_patch.undo()
