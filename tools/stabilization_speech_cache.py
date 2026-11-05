"""Compare cold and validated warm detector runs on real media, without AI."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',action='append',required=True,help='label=path')
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    os.environ['DESCRIBER_HOME']=str(args.output/'isolated-home')
    from describer.engine.core import protected_audio,sha
    from describer.project import Project
    from describer.services import DEFAULTS,probe
    settings=dict(DEFAULTS,sound_model=str(args.model))
    receipt={'source':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'working_candidate':True,'cases':[],
             'limits':['Actual whole-source YAMNet and FFmpeg, no AI inference/synthesis or factual-quality claim.','Cold and warm calls use the shared pipeline stage; files/models are hashed on every request.']}
    for case in args.case:
        label,path=case.split('=',1);project=Project(path,probe(path));messages=[];times=[];results=[];source_hash=sha(path)
        for _ in range(2):
            started=time.perf_counter();results.append(protected_audio(project,settings,None,messages.append));times.append(time.perf_counter()-started)
        assert results[0]==results[1] and any('Reusing validated' in s for s in messages)
        assert sha(path)==source_hash
        receipt['cases'].append({'label':label,'duration':project.duration,'source_sha256':source_hash,'cold_seconds':times[0],'warm_seconds':times[1],'identical_result':True,'classification_samples':len(results[0]['classification']),'protected_intervals':len(results[0]['protected']),'source_unchanged':True})
        (args.output/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')


if __name__=='__main__':main()
