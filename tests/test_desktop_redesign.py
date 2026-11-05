from describer.platforms import native_engine
"""Desktop redesign regressions: edit persistence, undo, range controls and export gate."""
import tempfile
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QLineEdit, QListWidget
from describer.app import Window
from describer.project import Cue


def make_window(tmp):
    app=QApplication.instance() or QApplication([])
    w=Window(Path(tmp)/'settings.json');w.settings.data['sounds']=False;w.error=lambda message: (_ for _ in ()).throw(AssertionError(message))
    w.project.video='fixture';w.project.duration=90
    w.project.cues=[Cue(10,14,'Original description.'),Cue(20,24,'Verify this.',disposition='unresolved',uncertainty='Identity uncertain')]
    w.refresh();w.choose(0)
    return app,w


def test_live_edits_undo_sort_and_save():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            w.text.setPlainText('Corrected description.')
            assert w.project.cues[0].text=='Corrected description.'
            w.undo_stack.undo();assert w.text.toPlainText()=='Original description.'
            w.undo_stack.redo();assert w.text.toPlainText()=='Corrected description.'
            w.start.setText('12');assert w.project.cues[0].start==12
            w.project_path=Path(tmp)/'save.adproject';assert w.save_project()
            from describer.project import Project
            assert Project.load(w.project_path).cues[0].start==12
            assert str(w.project_path.resolve()) in w.settings.data['recent_projects']
        finally:w.dirty=False;w.close();app.processEvents()


def test_add_review_filter_and_timeline_keyboard_targets():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            w.add_at_playhead();assert len(w.project.cues)==3
            w.cue_filter.setCurrentIndex(1);assert len(w.visible_indices)==2
            assert all(b.accessibleName().startswith('Description ') for b in w.timeline.blocks)
            w.choose(w.visible_indices[0]);w.mark_checked()
            assert len(w.visible_indices)==1
            w.undo_stack.undo();assert len(w.visible_indices)==2
        finally:w.dirty=False;w.close();app.processEvents()


def test_export_blocks_unresolved_media_but_allows_text():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp);observed=[]
        def inspect():
            d=QApplication.activeModalWidget();assert isinstance(d,QDialog)
            formats=d.findChildren(QListWidget)[0]
            path=next(x for x in d.findChildren(QLineEdit) if x.accessibleName()=='Export save path')
            go=next(x for x in d.findChildren(QPushButton) if x.text()=='Export')
            path.setText(str(Path(tmp)/'output.mp4'));observed.append(not go.isEnabled())
            formats.setCurrentRow(5);path.setText(str(Path(tmp)/'output.txt'));observed.append(go.isEnabled());d.reject()
        try:
            QTimer.singleShot(0,inspect);w.export();assert observed==[True,True]
        finally:w.dirty=False;w.close();app.processEvents()


def test_settings_categories_and_draft_cancel_keep_widgets_alive():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        def close():QApplication.activeModalWidget().reject()
        try:
            QTimer.singleShot(0,close);w.edit_settings('Developer API')
            QTimer.singleShot(0,close);w.draft_dialog()
            assert w.model_picker.scope.count()==3
            w.refresh();assert w.project.cues[0].text=='Original description.'
        finally:w.dirty=False;w.close();app.processEvents()


def test_timeline_zoom_scroll_and_selection_follow():
    from PySide6.QtCore import QPointF, QPoint, Qt
    from PySide6.QtGui import QWheelEvent
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            w.project.duration=600;w.timeline.view_seconds=90;w.timeline.resize(800,238);w.timeline.set_view(200)
            anchor=w.timeline.seconds_at(400);old_span=w.timeline.span()
            event=QWheelEvent(QPointF(400,80),QPointF(400,80),QPoint(),QPoint(0,120),Qt.NoButton,Qt.ControlModifier,Qt.NoScrollPhase,False)
            w.timeline.wheelEvent(event)
            assert w.timeline.span()<old_span
            assert abs(w.timeline.seconds_at(400)-anchor)<.002
            w.timeline.ensure_visible(550)
            assert w.timeline.view_start<=550<w.timeline.view_start+w.timeline.span()
            w.choose(0)
            assert w.timeline.view_start<=10<w.timeline.view_start+w.timeline.span()
        finally:w.dirty=False;w.close();app.processEvents()


def test_visual_hierarchy_start_state_caption_and_fit_spacing():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            w.show();app.processEvents();w.show_start();app.processEvents()
            assert not w.editor_toolbar.isVisible()
            assert w.recent_empty.isVisible()
            for name in ('Theme','Settings'):
                control=next(b for b in w.findChildren(QPushButton) if b.accessibleName()==name)
                assert not control.text() and control.property('role')=='ghost'
            w.pages.setCurrentIndex(1);w.current.setText('');w.presentation_position(0)
            assert not w.current.isVisible()
            w.presentation_position(10000)
            assert w.current.isVisible()
            cues=w.project.cues;w.project.cues=[];w.refresh();assert not w.current.isVisible();w.project.cues=cues;w.refresh()
            assert not w.fit_bar.isTextVisible()
            assert w.fit_label.geometry().bottom()<w.fit_bar.geometry().top()
            assert w.export_button.property('role')=='primary'
            assert w.cue_list.item(0).data(256).text=='Original description.'
        finally:w.dirty=False;w.close();app.processEvents()


def test_review_action_start_counts_and_multiline_prompt():
    from PySide6.QtWidgets import QPlainTextEdit
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            w.show();w.choose(0);app.processEvents();assert not w.checked_button.isVisible()
            w.choose(1);assert w.checked_button.isVisible()
            w.show_start();w.update_status();assert 'In gap' not in w.state_label.text() and 'Review' not in w.state_label.text()
            w.pages.setCurrentIndex(1);w.update_status();assert 'Review 1' in w.state_label.text()
            assert isinstance(w.prompt,QPlainTextEdit)
            w.prompt.setPlainText('First instruction.\nSecond instruction.');assert '\n' in w.prompt.toPlainText()
            assert w.question.placeholderText()
        finally:w.dirty=False;w.close();app.processEvents()


def test_export_voice_picker_selects_ids_for_the_correct_engine():
    import time
    from unittest.mock import patch
    from describer.desktop import ExportVoices
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        with patch('describer.windows_speech.windows_speech',side_effect=lambda engine,**kwargs:[{'name':engine+' test voice','id':engine+'-id'}]):
            d=QDialog(w);picker=ExportVoices(w,d)
            def finish():
                deadline=time.monotonic()+3
                while picker.loading and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
                assert not picker.loading
            try:
                finish();picker.voice.setCurrentIndex(1);assert picker.selection()['windows_voice']==native_engine()+'-id'
                picker.engine.addItem('Windows OneCore') if picker.engine.findText('Windows OneCore')<0 else None;picker.engine.setCurrentText('Windows OneCore');finish();picker.voice.setCurrentIndex(1)
                assert picker.selection()=={'voice_engine':'Windows OneCore','windows_voice':'Windows OneCore-id','voice_preset':''}
                picker.engine.setCurrentText('OpenAI');assert picker.voice.count()>0
                assert picker.selection()['voice_engine']=='OpenAI'
                assert w.settings.data['voice_engine']==native_engine()  # Cancel never mutates settings.
            finally:
                # Keep the owner alive even if an assertion fails during discovery.
                stopped=picker.shutdown(wait_ms=5000);app.processEvents()
                assert stopped,'Voice discovery did not stop during test teardown'
                d.close();w.dirty=False;w.close();app.processEvents()


def test_edit_preserves_review_evidence_through_undo_save_and_check(tmp_path):
    from describer.project import Project
    app,w=make_window(tmp_path)
    try:
        original=Cue(20,24,'Verify this.',event_id='event-a',event_start=18,event_end=25,
                     evidence='Visible shape',uncertainty='Identity uncertain',disposition='unresolved',
                     audio='old.wav',speech_seconds=2,speed=1.1)
        w.project.cues=[original];w.refresh();w.choose(0)
        w.text.setPlainText('Verify this!')
        edited=w.project.cues[0]
        assert (edited.disposition,edited.uncertainty,edited.evidence)==('unresolved','Identity uncertain','Visible shape')
        assert (edited.event_id,edited.event_start,edited.event_end)==('event-a',18,25)
        assert (edited.audio,edited.speech_seconds,edited.speed)==('',0,1)
        w.undo_stack.undo();assert w.project.cues[0]==original
        w.undo_stack.redo();assert w.project.cues[0]==edited
        w.start.setText('21');assert w.project.cues[0].event_start==18
        path=tmp_path/'review.adproject';w.project.save(path)
        assert Project.load(path).cues[0]==w.project.cues[0]
        w.mark_checked();assert not w.project.cues[0].uncertainty
        assert w.project.cues[0].disposition=='unplanned'
        w.undo_stack.undo();assert w.project.cues[0].disposition=='unresolved'
    finally:w.dirty=False;w.close();app.processEvents()


def test_voice_discovery_waits_for_owned_completion_before_replacement(tmp_path):
    import threading
    import time
    from unittest.mock import patch
    from describer.desktop import ExportVoices
    entered=threading.Event();release=threading.Event()
    def discover(engine,**kwargs):
        entered.set();assert release.wait(3)
        return [{'name':engine,'id':engine}]
    app,w=make_window(tmp_path);d=QDialog(w)
    with patch('describer.windows_speech.windows_speech',side_effect=discover):
        picker=ExportVoices(w,d)
        try:
            assert entered.wait(3)
            first=picker.thread
            picker.engine.addItem('Windows OneCore') if picker.engine.findText('Windows OneCore')<0 else None;picker.engine.setCurrentText('Windows OneCore')
            assert picker.thread is first
            release.set()
            # Deliberately hold the GUI queue until the old native thread ends.
            assert first.wait(3000)
            picker.engine.addItem('Windows 32-bit') if picker.engine.findText('Windows 32-bit')<0 else None;picker.engine.setCurrentText('Windows 32-bit')
            assert picker.thread is first
            deadline=time.monotonic()+3
            while picker.loading and time.monotonic()<deadline:
                app.processEvents();time.sleep(.01)
            assert not picker.loading and picker.loaded=='Windows 32-bit'
            picker.engine.setCurrentIndex(0)
            picker.shutdown()
            deadline=time.monotonic()+3
            while picker.thread is not None and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
            assert picker.thread is None or not picker.thread.isRunning()
            app.processEvents()
        finally:
            release.set()
            stopped=picker.shutdown(wait_ms=5000)
            app.processEvents()
            assert stopped, 'Voice discovery did not stop during test teardown'
            d.close();w.dirty=False;w.close();app.processEvents()
