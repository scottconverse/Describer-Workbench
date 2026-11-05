"""Native real-media preservation workflow. Proposed cues are explicit fixtures,
not a model-quality claim; no provider/credentials are substituted or called.
"""
import argparse
import copy
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    from PySide6.QtCore import QTimer, QUrl
    from PySide6.QtWidgets import QApplication, QCheckBox, QDialogButtonBox
    from PySide6.QtTest import QTest
    from describer.app import Window
    from describer.project import Cue, Project
    from describer.drafting import fingerprint
    from describer.engine.core import sha
    app = QApplication.instance() or QApplication([])
    receipt = {'platform': sys.platform, 'qt_platform': app.platformName(), 'source_sha256': sha(args.source),
               'limits': ['Fixture proposals exercise real UI/merge/save/undo. No live AI accuracy or screen-reader claim.']}
    with tempfile.TemporaryDirectory(prefix='describer-stabilization-') as tmp:
        window = Window(Path(tmp)/'settings.json')
        window.settings.data['sounds'] = False
        window.show()
        try:
            frames = []
            window.video.videoSink().videoFrameChanged.connect(lambda frame: frames.append(True) if frame.isValid() else None)
            window.set_video(args.source)
            window.audio.setMuted(True)
            window.player.play()
            deadline = time.monotonic()+15
            while not frames and time.monotonic() < deadline:
                app.processEvents()
                QTest.qWait(30)
            assert frames, window.player.errorString()
            window.player.pause()
            duration = window.project.duration
            assert duration > 80
            old = [Cue(2,4,'Outside the draft.',event_id='outside',origin='manual',manually_edited=True),
                   Cue(18,22,'Crosses the boundary.',event_id='boundary',review_status='approved'),
                   Cue(22,24,'Reviewed observation.',event_id='reviewed',review_status='reviewed'),
                   Cue(70,74,'Approved after the range.',event_id='after',review_status='approved')]
            window.project.cues = [c.validate(duration) for c in old]
            window.project.coverage = [{'event_id':c.event_id, 'cue_id':c.cue_id, 'text':c.text, 'evidence':'Retained fixture evidence'} for c in old]
            window.project.glossary = 'Astronaut: white spacesuit'
            window.project.analysis = {'usage':[{'operation':'describe','total_tokens':10}]}
            window.refresh()
            original = copy.deepcopy(window.project)
            proposed = Project(original.video,duration,[Cue(22,24,'Explicitly accepted replacement.').validate(duration),Cue(35,37,'A new observation.').validate(duration)],'Astronaut: different proposal',analysis={'usage':original.analysis['usage']+[{'total_tokens':5}]})
            failures = []
            def operate():
                try:
                    dialog = QApplication.activeModalWidget()
                    boxes = dialog.findChildren(QCheckBox)
                    boundary = next(b for b in boxes if b.text().startswith('Replace existing') and 'Crosses the boundary.' in b.text()) if any('Crosses the boundary.' in b.text() for b in boxes) else None
                    if boundary:assert not boundary.isEnabled()
                    replacement = next(b for b in boxes if b.text().startswith('Replace existing') and 'Reviewed observation.' in b.text())
                    assert not replacement.isChecked()
                    replacement.click()
                    next(b for b in boxes if b.text().startswith('Use proposed') and 'Explicitly accepted replacement.' in b.text()).click()
                    assert not next(b for b in boxes if b.text().startswith('Use the proposed glossary')).isChecked()
                    dialog.grab().save(str(args.output/'draft-review.png'))
                    dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Apply).click()
                except Exception as exc:
                    failures.append(str(exc))
                    QApplication.activeModalWidget().reject()
            QTimer.singleShot(0, operate)
            window.generated({'project':proposed,'original':fingerprint(original),'start':20,'end':40})
            assert not failures, failures
            assert len(window.project.cues) == 5
            for before in (old[0],old[1],old[3]):
                assert asdict(next(c for c in window.project.cues if c.cue_id == before.cue_id)) == asdict(before)
            assert window.project.glossary == original.glossary
            accepted = copy.deepcopy(window.project)
            window.project_path = args.output/'accepted.adproject'
            assert window.save_project()
            assert asdict(Project.load(window.project_path)) == asdict(accepted)
            window.undo_stack.undo()
            assert asdict(window.project) == asdict(original)
            window.undo_stack.redo()
            assert asdict(window.project) == asdict(accepted)
            receipt.update(decoded_video_frames=len(frames), retained_cues=3, accepted_cues=2,
                           original_glossary_preserved=True, whole_project_undo_redo=True, save_reopen=True,
                           source_unchanged=sha(args.source)==receipt['source_sha256'])
            assert receipt['source_unchanged']
            window.grab().save(str(args.output/'accepted-workbench.png'))
        finally:
            window.player.setSource(QUrl())
            window.dirty = False
            window.close()
            app.processEvents()
    (args.output/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__ == '__main__':main()
