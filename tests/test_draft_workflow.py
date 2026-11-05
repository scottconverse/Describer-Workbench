import copy
import tempfile
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QCheckBox,QComboBox,QLineEdit,QLabel,QPushButton
from describer.providers import PROVIDERS
from test_desktop_redesign import make_window


def test_simple_path_and_cancel_preserve_advanced_settings(tmp_path):
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp);before=copy.deepcopy(w.settings.data);prompt=w.prompt.toPlainText();observed=[]
        def interact():
            d=QApplication.activeModalWidget()
            try:
                exact=next(x for x in d.findChildren(QLineEdit) if x.accessibleName()=='Exact analysis model ID')
                advanced=next(x for x in d.findChildren(QCheckBox) if x.accessibleName()=='Show advanced draft controls')
                connection=next(x for x in d.findChildren(QComboBox) if x.accessibleName()=='Draft connection')
                assert tuple(connection.itemText(i) for i in range(connection.count()))==PROVIDERS
                assert not exact.isVisible()
                note=next(x for x in d.findChildren(QLabel) if x.accessibleName()=='Draft transmission and preservation')
                assert note.isVisible() and 'video, with audio unless removed' in note.text()
                d.grab().save(str(tmp_path/'draft-simple.png'))
                connection.setCurrentText('Codex CLI');assert 'Codex CLI' in note.text() and 'no audio' in note.text()
                advanced.click();assert exact.isVisible();exact.setText('explicit-model')
                w.prompt.setPlainText('Changed editorial direction')
                d.grab().save(str(tmp_path/'draft-advanced.png'))
                advanced.click();assert not exact.isVisible() and note.isVisible()
                assert 'explicit-model' in next(x for x in d.findChildren(QLabel) if x.accessibleName()=='Selected draft model').text()
                observed.append(True)
            finally:d.reject()
        try:
            QTimer.singleShot(0,interact);w.draft_dialog()
            assert observed and w.settings.data==before and w.prompt.toPlainText()==prompt
        finally:w.dirty=False;w.close();app.processEvents()


def test_start_uses_exact_model_and_range_after_advanced_collapses():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp);errors=[]
        def interact():
            d=QApplication.activeModalWidget()
            try:
                connection=next(x for x in d.findChildren(QComboBox) if x.accessibleName()=='Draft connection');connection.setCurrentText('Codex CLI')
                exact=next(x for x in d.findChildren(QLineEdit) if x.accessibleName()=='Exact analysis model ID');exact.setText('explicit-model')
                scope=next(x for x in d.findChildren(QComboBox) if x.accessibleName()=='Analysis range');scope.setCurrentIndex(2)
                next(x for x in d.findChildren(QPushButton) if x.text()=='Start draft').click()
            except Exception as exc:errors.append(exc);d.reject()
        try:
            with patch.object(w,'analyze') as analyze:
                QTimer.singleShot(0,interact);w.draft_dialog()
                assert not errors,errors;analyze.assert_called_once()
            assert w.settings.data['analysis_provider']=='Codex CLI' and w.settings.data['provider_models']['Codex CLI']=='explicit-model'
            assert w.model_picker.scope.currentIndex()==2
        finally:w.dirty=False;w.close();app.processEvents()
