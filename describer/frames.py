"""Bounded image extraction with source timestamps, without fps-filter retiming."""
import math
import re
from pathlib import Path


def sample(video,root,interval,cancel):
    from .services import run,tool
    interval=float(interval)
    if not math.isfinite(interval) or interval<=0:raise ValueError('Frame sampling interval must be positive and finite.')
    # fps chooses interval-centred source frames and rewrites their PTS. select
    # preserves the source time; showinfo reports it before image encoding.
    trace=run([tool('ffmpeg'),'-hide_banner','-nostats','-loglevel','info','-y','-i',str(video),
               '-vf',f'select=isnan(prev_selected_t)+gte(t-prev_selected_t\\,{interval}),showinfo,scale=640:-2',
               '-fps_mode','vfr','-frames:v','8','-q:v','3',str(Path(root)/'%03d.jpg')],cancel,return_stderr=True)
    files=sorted(Path(root).glob('*.jpg'))
    times=[float(value) for value in re.findall(r'\bn:\s*\d+.*?pts_time:([-+\d.eE]+)',trace.decode(errors='replace'))][:len(files)]
    if not files or len(times)!=len(files) or any(not math.isfinite(t) or t<0 for t in times):
        raise ValueError('Could not extract timestamped video frames; no inferred frame times were sent.')
    return list(zip(files,times))
