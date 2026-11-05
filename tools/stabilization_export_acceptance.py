"""Actual native synthesis, measured placement and decoded export comparison."""
import argparse
import json
import os
from pathlib import Path
import sys
import threading

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    os.environ['DESCRIBER_HOME']=str(args.output/'isolated-home')
    from describer.engine.core import prepare,Checkpoints,sha
    from describer.engine.exporting import export
    from describer.export_preview import outcome
    from describer.project import Cue,Project
    from describer.services import DEFAULTS,run,tool,probe
    from describer.platforms import native_engine
    source=args.output/'source.mp4'
    run([tool('ffmpeg'),'-v','error','-y','-f','lavfi','-i','color=c=blue:s=160x120:r=30:d=4','-f','lavfi','-i','sine=frequency=220:duration=4','-c:v','libx264','-c:a','aac','-shortest',str(source)])
    original=sha(source);cancel=threading.Event();settings=dict(DEFAULTS,sound_model=str(args.model),voice_engine=native_engine())
    root=args.output/'measured';checkpoint=Checkpoints(root,{'fixture':'native-export-preview'})
    project=Project(str(source),probe(source),[Cue(1,1.5,'A person carefully lifts a small brass key out of the mud and examines it in the fading afternoon light.')])
    prepare(project,settings,root,cancel,print,checkpoint)
    preview=outcome(project,settings,'mp4');assert preview['measured'] and preview['extended_seconds']>0
    measured={}
    for suffix in ('wav','mp4'):
        target=args.output/('complete.'+suffix);receipt=export(project,target,settings,cancel,print)
        info=json.loads(run([tool('ffprobe'),'-v','error','-show_format','-of','json',str(target)]))
        actual=float(info['format']['duration']);assert abs(actual-preview['finished_seconds'])<.15
        run([tool('ffmpeg'),'-v','error','-i',str(target),'-f','null','-'])
        measured[suffix]={'decoded':True,'duration':actual,'receipt':receipt}
    assert sha(source)==original
    project.save(args.output/'measured.adproject')
    restored=Project.load(args.output/'measured.adproject');assert outcome(restored,settings,'mp4')==preview
    (args.output/'receipt.json').write_text(json.dumps({'native_engine':settings['voice_engine'],'preview':preview,'exports':measured,'source_unchanged':True,'saved_reopened_preview_identical':True,'limits':['Controlled visual fixture, real installed native voice and YAMNet/FFmpeg; no AI accuracy or human-listening claim.']},indent=2),encoding='utf-8')


if __name__=='__main__':main()
