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


def _meeting_box(d):
    return next(x for x in d.findChildren(QCheckBox) if x.accessibleName()=='Public meeting mode')


def test_meeting_mode_switch_is_visible_and_saved_on_start():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp);errors=[];w.settings.data['drafting_mode']=''
        def interact():
            d=QApplication.activeModalWidget()
            try:
                box=_meeting_box(d);assert box.isVisible() and not box.isChecked()
                box.setChecked(True)
                next(x for x in d.findChildren(QLineEdit) if x.accessibleName()=='Exact analysis model ID').setText('explicit-model')
                next(x for x in d.findChildren(QPushButton) if x.text()=='Start draft').click()
            except Exception as exc:errors.append(exc);d.reject()
        try:
            with patch.object(w,'analyze') as analyze:
                QTimer.singleShot(0,interact);w.draft_dialog()
                assert not errors,errors;analyze.assert_called_once()
            assert w.settings.data['drafting_mode']=='Public meeting'
        finally:w.dirty=False;w.close();app.processEvents()


def test_meeting_mode_switch_shows_saved_mode_and_cancel_keeps_it():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp);seen=[];w.settings.data['drafting_mode']='Public meeting'
        def interact():
            d=QApplication.activeModalWidget()
            try:box=_meeting_box(d);seen.append(box.isChecked());box.setChecked(False)
            finally:d.reject()
        try:
            QTimer.singleShot(0,interact);w.draft_dialog()
            assert seen==[True] and w.settings.data['drafting_mode']=='Public meeting'
        finally:w.dirty=False;w.close();app.processEvents()


def _named(d,kind,name):
    return next(x for x in d.findChildren(kind) if x.accessibleName()==name)


def test_captions_file_is_chosen_in_the_window_and_kept_for_this_video(tmp_path):
    srt=tmp_path/'meeting.srt';srt.write_text('1\n00:00:01,000 --> 00:00:02,000\nAll in favor?\n',encoding='utf-8')
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp);errors=[]
        def interact():
            d=QApplication.activeModalWidget()
            try:
                field=_named(d,QLineEdit,'Captions file');assert field.isVisible() and field.text()==''
                with patch('describer.desktop.QFileDialog.getOpenFileName',return_value=(str(srt),'')):
                    _named(d,QPushButton,'Choose captions file').click()
                assert field.text()==str(srt)
                _named(d,QLineEdit,'Exact analysis model ID').setText('explicit-model')
                next(x for x in d.findChildren(QPushButton) if x.text()=='Start draft').click()
            except Exception as exc:errors.append(exc);d.reject()
        try:
            with patch.object(w,'analyze'):
                QTimer.singleShot(0,interact);w.draft_dialog()
            assert not errors,errors
            assert w.settings.data['captions']==str(srt) and w.settings.data['captions_video']=='fixture'
        finally:w.dirty=False;w.close();app.processEvents()


def test_captions_clear_button_and_missing_file_is_refused(tmp_path):
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp);errors=[];messages=[]
        w.settings.data.update(captions=str(tmp_path/'gone.vtt'),captions_video='fixture');w.error=messages.append
        def interact():
            d=QApplication.activeModalWidget()
            try:
                field=_named(d,QLineEdit,'Captions file');assert field.text().endswith('gone.vtt')
                _named(d,QLineEdit,'Exact analysis model ID').setText('explicit-model')
                next(x for x in d.findChildren(QPushButton) if x.text()=='Start draft').click()
                assert d.isVisible() and messages and 'captions' in messages[-1].lower()
                _named(d,QPushButton,'Clear captions file').click();assert field.text()==''
                next(x for x in d.findChildren(QPushButton) if x.text()=='Start draft').click()
            except Exception as exc:errors.append(exc);d.reject()
        try:
            with patch.object(w,'analyze'):
                QTimer.singleShot(0,interact);w.draft_dialog()
            assert not errors,errors
            assert w.settings.data['captions']=='' and w.settings.data['captions_video']==''
        finally:w.dirty=False;w.close();app.processEvents()


def test_opening_another_video_forgets_captions_for_the_old_video(tmp_path):
    other=tmp_path/'other.mp4';other.write_bytes(b'')
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            w.settings.data.update(captions='a.srt',captions_video=str(other.resolve()))
            with patch('describer.services.probe',return_value=30.0):w.set_video(str(other))
            assert w.settings.data['captions']=='a.srt'
            w.settings.data.update(captions='a.srt',captions_video='old.mp4')
            with patch('describer.services.probe',return_value=30.0):w.set_video(str(other))
            assert w.settings.data['captions']=='' and w.settings.data['captions_video']==''
            w.settings.data.update(captions='hand.srt',captions_video='')
            with patch('describer.services.probe',return_value=30.0):w.set_video(str(other))
            assert w.settings.data['captions']=='hand.srt'
        finally:w.dirty=False;w.close();app.processEvents()
