"""Opt-in native media acceptance; uses supplied local clips/assets, never live data."""
import argparse
import os
import time
from pathlib import Path

from describer.engine import DescriptionService
from describer.engine.core import atomic_json, sha


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--clips',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--sound-model',required=True);parser.add_argument('--model',default='gemma4:12b')
    args=parser.parse_args()
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    settings={'analysis_provider':'Ollama','ollama_model':args.model,'sound_model':str(Path(args.sound_model).resolve()),'voice_engine':'Windows'}
    service=DescriptionService(output/'engine',settings)
    receipt={'pid':os.getpid(),'started':time.time(),'expected':'three completed120s clips, protected placement, actual complete MP4 exports, one checkpoint resume',
             'cancel':'Create CANCEL in this output folder; the script requests cooperative cancellation and closes its own service.',
             'settings':settings,'clips':[]}
    atomic_json(output/'run.json',receipt)
    try:
        for index,name in enumerate(('big-buck-bunny','tears-of-steel','sintel')):
            source=Path(args.clips).resolve()/(name+'.mp4');original=sha(source)
            job=service.submit(source=str(source))
            receipt['active_job']=job['id'];atomic_json(output/'run.json',receipt)
            interrupted=False;previous=None
            while True:
                state=service.get_job(job['id'])
                if state['progress']!=previous:
                    previous=state['progress'];print(name,state['state'],previous,flush=True)
                if (output/'CANCEL').exists():service.cancel(job['id'])
                # Prove actual model-request checkpoint reuse, not a mocked resume.
                if index==0 and not interrupted and list((output/'engine'/job['id']/'stages').glob('observe-*.json')):
                    service.cancel(job['id'])
                    while not service._futures[job['id']].done():time.sleep(.05)
                    checkpoint=next((output/'engine'/job['id']/'stages').glob('observe-*.json'))
                    before=(sha(checkpoint),checkpoint.stat().st_mtime_ns)
                    service.resume(job['id']);interrupted=True
                    receipt['resume']={'id':job['id'],'checkpoint':str(checkpoint),'before':before}
                    atomic_json(output/'run.json',receipt)
                    continue
                if state['state'] in ('done','error','cancelled','interrupted'):break
                time.sleep(.2)
            result=service.wait(job['id'])
            if index==0:
                checkpoint=Path(receipt['resume']['checkpoint'])
                assert (sha(checkpoint),checkpoint.stat().st_mtime_ns)==tuple(receipt['resume']['before'])
                receipt['resume']['verified']=True
            protected=result.analysis['protected']
            for cue in result.cues:
                if cue.disposition=='in-gap':
                    assert not any(cue.start<b-1e-5 and cue.end>a+1e-5 for a,b in protected)
                    assert cue.event_start<=cue.start<=cue.end<=cue.event_end+.001
                    assert cue.speed<=1.15
            summary={'name':name,'job_id':job['id'],'source_sha256':original,'coverage':service.coverage(job['id'])['counts'],
                     'observations':len(result.cues),'placement_verified':True}
            # Uncertainty is preserved. A complete export must refuse unresolved
            # observations rather than silently claim complete visual coverage.
            mode='in-gap-only' if any(c.disposition=='unresolved' for c in result.cues) else 'complete'
            exported=service.export_job(job['id'],'mp4',mode=mode)
            service.wait(exported['id'],log=lambda message:print(name,'export',message,flush=True))
            summary['export']=service.get_job(exported['id'])['artifact']
            from describer.services import run,tool
            run([tool('ffmpeg'),'-v','error','-i',summary['export']['path'],'-f','null','-'])
            summary['output_decoded']=True
            assert sha(source)==original
            summary['original_unchanged']=True
            receipt['clips'].append(summary);atomic_json(output/'run.json',receipt)
        receipt.update(finished=time.time(),state='passed',active_job=None)
        atomic_json(output/'run.json',receipt)
        print('Native verification completed',flush=True)
    except Exception as exc:
        receipt.update(state='failed',error=str(exc),finished=time.time())
        atomic_json(output/'run.json',receipt)
        raise
    finally:service.close()


if __name__=='__main__':main()
