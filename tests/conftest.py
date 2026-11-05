"""Run routine Qt tests offscreen and retain one application across the session."""
import os
import pytest

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')


@pytest.fixture(scope='session',autouse=True)
def qt_application_lifetime():
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance() or QApplication([])
    yield app
    app.processEvents()
