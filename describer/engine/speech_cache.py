"""Disposable speech-analysis reuse. Captions are applied afresh by the caller."""
import hashlib
import json
import math
from pathlib import Path
import sys
import time

from .assets import default_root


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()


def validate(value,duration):
    if not isinstance(value,dict) or set(value)!= {'spans','trace'}:raise ValueError('Invalid cached speech result.')
    end=-1
    for a,b in value['spans']:
        if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in (a,b)) or not 0<=a<b<=duration or a<end:raise ValueError('Invalid protected interval.')
        end=b
    point=-1
    for row in value['trace']:
        current=row['time']
        if not isinstance(current,(int,float)) or not math.isfinite(current) or not point<current<duration:raise ValueError('Invalid classification time.')
        if any(not isinstance(row[k],(int,float)) or not math.isfinite(row[k]) or not 0<=row[k]<=1 for k in ('speech','vocal','music')):raise ValueError('Invalid classification score.')
        point=current


def measured(source,duration,model,cancel,log,analyze,root=None):
    from .core import atomic_json,check_cancel,sha
    import portalocker
    from . import sound
    from ..services import tool
    check_cancel(cancel)
    # Hash actual bytes on every request; paths/mtime alone are not identity.
    identity={'schema':1,'source':sha(source),'duration':duration,'model':sha(model),
              'implementation':sha(sys.executable if getattr(sys,'frozen',False) else Path(sound.__file__)),'ffmpeg':sha(tool('ffmpeg')),
              'runtime':__import__('onnxruntime').__version__,'numpy':__import__('numpy').__version__}
    def fresh():
        check_cancel(cancel)
        spans,trace=analyze(source,duration,model,cancel)
        value={'spans':spans,'trace':trace};validate(value,duration);check_cancel(cancel)
        if sha(source)!=identity['source'] or sha(model)!=identity['model']:raise ValueError('Source or detector changed during speech analysis.')
        return spans,trace
    root=Path(root or default_root()/'speech-cache').resolve()
    try:root.mkdir(parents=True,exist_ok=True)
    except OSError:
        log('Speech cache is unavailable; measuring the source without reuse.')
        return fresh()
    key=digest(identity);path=root/(key+'.json')
    lock=portalocker.Lock(str(root/(key+'.lock')),timeout=0)
    while True:
        check_cancel(cancel)
        try:lock.acquire();break
        except portalocker.exceptions.LockException:time.sleep(.1)
        except OSError:
            log('Speech cache lock is unavailable; measuring without reuse.')
            return fresh()
    try:
        check_cancel(cancel)
        if path.is_file() and not path.is_symlink():
            try:
                if path.stat().st_size>32*1024*1024:raise ValueError('Oversized cache entry.')
                cached=json.loads(path.read_text(encoding='utf-8'))
                value=cached['value']
                if cached['identity']!=identity or cached['digest']!=digest(value):raise ValueError('Speech cache identity/digest mismatch.')
                validate(value,duration);check_cancel(cancel)
                log('Reusing validated speech and vocal analysis for this source.')
                return value['spans'],value['trace']
            except (OSError,ValueError,KeyError,TypeError):
                log('Speech-analysis cache rejected; measuring the source again.')
        check_cancel(cancel)
        spans,trace=fresh()
        value={'spans':spans,'trace':trace}
        try:
            if path.is_symlink():raise OSError('Speech cache target is a symbolic link.')
            atomic_json(path,{'identity':identity,'value':value,'digest':digest(value)})
        except OSError as exc:log('Speech measured; reusable cache could not be saved: '+str(exc))
        return spans,trace
    finally:lock.release()
