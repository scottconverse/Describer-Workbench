"""Native real-media crash/restart acceptance with an isolated settings folder."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--child',action='store_true');args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    from describer.engine.core import sha
    original_hash=sha(args.video)
    if not args.child:
        result=subprocess.run([sys.executable,__file__,str(args.video),str(args.output),'--child'],timeout=90)
        if result.returncode!=23:raise RuntimeError('Crash fixture did not reach its intended terminal point: '+str(result.returncode))
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication,QInputDialog
    from describer.app import Window
    from describer.project import Cue,Project
    app=QApplication([]);w=Window(args.output/'settings.json');w.settings.data['sounds']=False
    if args.child:
        w.set_video(args.video);cue=Cue(10,14,'Fixture astronaut description.',review_status='approved').validate(w.project.duration)
        w.project.cues=[cue];w.project.glossary='Fixture: original glossary';w.project.analysis={'fixture':'crash recovery'}
        w.refresh();w.choose(0);w.save_project(destination=args.output/'original.adproject')
        w.text.setPlainText('Edited fixture astronaut description.')
        assert w.recovery_timer.interval()==30000
        w.show()
        def crash():
            rows=w.draft_store.entries()
            assert rows,'Real 30-second recovery timer did not produce a snapshot.'
            (args.output/'expected.json').write_text(json.dumps(asdict(w.project)),encoding='utf-8')
            w.grab().save(str(args.output/'before-crash.png'))
            os._exit(23)
        QTimer.singleShot(32000,crash)
        app.exec()
        raise RuntimeError('Crash fixture closed before snapshot.')
    def accept():
        dialog=QApplication.activeModalWidget()
        assert isinstance(dialog,QInputDialog)
        dialog.accept()
    QTimer.singleShot(150,accept);w.recover_unsaved()
    expected=json.loads((args.output/'expected.json').read_text(encoding='utf-8'))
    assert asdict(w.project)==expected and w.project_path is None and w.dirty
    assert w.project.cues[0].review_status=='needs-review'
    assert w.save_project(destination=args.output/'recovered-copy.adproject')
    assert Project.load(args.output/'original.adproject').cues[0].text=='Fixture astronaut description.'
    assert Project.load(args.output/'recovered-copy.adproject').cues[0].text=='Edited fixture astronaut description.'
    assert sha(args.video)==original_hash
    w.show();app.processEvents();w.grab().save(str(args.output/'recovered.png'))
    receipt={'platform':sys.platform,'qt_platform':app.platformName(),'actual_timer_ms':30000,'child_exit':23,'full_project_restored':True,'review_history_restored':True,'original_project_unchanged':True,'source_sha256':original_hash,'source_unchanged':True,'limits':['Fixture descriptions, actual native Qt/video/timer/file recovery. No AI or human reader claim.']}
    (args.output/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    w.dirty=False;w.close();app.processEvents()


if __name__=='__main__':main()
