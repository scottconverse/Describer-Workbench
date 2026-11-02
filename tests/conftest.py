"""Keep one native Qt application alive across GUI tests and media backends."""
import pytest


@pytest.fixture(scope='session',autouse=True)
def qt_application_lifetime():
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance() or QApplication([])
    yield app
    app.processEvents()
