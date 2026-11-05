import copy
import tempfile
from unittest.mock import patch

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QLabel,QPushButton,QListWidget,QLineEdit

from describer.export_preview import outcome,plan_stamp
from describer.project import Project,Cue
from test_desktop_redesign import make_window


def test_measured_plan_invalidation_and_format_semantics(tmp_path):
    source=tmp_path/'video';source.write_bytes(b'original')
    audio=tmp_path/'speech.wav';audio.write_bytes(b'measured fixture')
    project=Project(str(source),20,[Cue(2,3,'A description.',disposition='pause',audio=str(audio),speech_seconds=4)])
    settings={'voice_engine':'Windows SAPI','windows_voice':'chosen','speech_rate':0}
    project.analysis['export_plan_stamp']=plan_stamp(project,settings)
    project.save(tmp_path/'saved.adproject')
    assert outcome(Project.load(tmp_path/'saved.adproject'),settings,'mp4')['measured']
    assert outcome(project,settings,'mp4')['finished_seconds']==24
    assert 'freezes' in outcome(project,settings,'mp4')['text']
    for suffix in ('mp3','wav'):assert 'no picture' in outcome(project,settings,suffix)['text']
    for suffix in ('srt','vtt','txt','json'):assert not outcome(project,settings,suffix)['measured']
    assert not outcome(project,dict(settings,speech_rate=1),'wav')['measured']
    edited=copy.deepcopy(project);edited.cues[0].text='Changed';assert not outcome(edited,settings,'wav')['measured']
    project.cues[0].review_status='needs-review';assert outcome(project,settings,'wav')['blocked']
    project.cues[0].review_status='unreviewed'
    audio.unlink();assert not outcome(project,settings,'wav')['measured']


def test_export_dialog_measurement_preserves_selection_and_cancel(tmp_path):
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp);w.project.cues=w.project.cues[:1];w.settings.data['voice_engine']='OpenAI'
        before=copy.deepcopy(w.settings.data);observed=[]
        def interact():
            d=QApplication.activeModalWidget()
            try:
                formats=d.findChild(QListWidget);formats.setCurrentRow(2)
                next(x for x in d.findChildren(QLineEdit) if x.accessibleName()=='Export save path').setText(str(tmp_path/'chosen.wav'))
                label=next(x for x in d.findChildren(QLabel) if x.accessibleName()=='Export outcome preview')
                assert 'not been measured' in label.text()
                d.grab().save(str(tmp_path/'export-preview.png'))
                next(x for x in d.findChildren(QPushButton) if x.text()=='Measure narration').click();observed.append(True)
            finally:d.reject()
        try:
            with patch.object(w,'repair_narration') as measure:
                QTimer.singleShot(0,interact);w.export()
                assert observed;measure.assert_called_once()
                assert measure.call_args.kwargs['settings_override']['voice_engine']=='OpenAI'
                with patch.object(w,'export') as reopen:
                    measure.call_args.kwargs['completed']()
                    assert reopen.call_args.kwargs['initial_format']=='wav'
                    assert reopen.call_args.kwargs['initial_path']==str(tmp_path/'chosen.wav')
            assert w.settings.data==before
        finally:w.dirty=False;w.close();app.processEvents()


def test_measurement_does_not_overwrite_edits_made_during_job():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp);callbacks=[];messages=[]
        try:
            with patch.object(w,'operation_preflight',side_effect=lambda settings,launch,**kwargs:launch()),patch.object(w,'job',side_effect=lambda work,done:callbacks.append(done)),patch.object(w,'notify',side_effect=messages.append):
                w.repair_narration()
                result=copy.deepcopy(w.project)
                w.project.cues[0].text='New manual work'
                callbacks[0](result)
            assert w.project.cues[0].text=='New manual work'
            assert messages and 'Current edits were kept' in messages[0]
        finally:w.dirty=False;w.close();app.processEvents()
