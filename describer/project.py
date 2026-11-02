import json
import math
import re
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


def seconds(value):
    if isinstance(value, str):
        parts = value.strip().replace(',', '.').split(':')
        result = sum(float(p) * 60 ** i for i, p in enumerate(reversed(parts)))
    else:
        result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError('Time must be a finite, nonnegative number.')
    return result


def stamp(value):
    ms = round(seconds(value) * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'


@dataclass
class Cue:
    start: float
    end: float
    text: str
    event_id: str = ''
    event_start: float | None = None
    event_end: float | None = None
    kind: str = 'action'
    evidence: str = ''
    uncertainty: str = ''
    disposition: str = 'unplanned'
    audio: str = ''
    speech_seconds: float = 0
    speed: float = 1

    def edited(self, start, end, text, duration=0):
        """Keep observation/review identity while invalidating changed narration."""
        from dataclasses import replace
        candidate = replace(self, start=start, end=end, text=text).validate(duration)
        if (candidate.start, candidate.end, candidate.text) != (self.start, self.end, self.text):
            candidate.audio = ''
            candidate.speech_seconds = 0
            candidate.speed = 1
            candidate.disposition = 'unresolved' if self.disposition == 'unresolved' or self.uncertainty else 'unplanned'
        return candidate

    def validate(self, duration=0):
        self.start, self.end = seconds(self.start), seconds(self.end)
        for name in ('text', 'event_id', 'kind', 'evidence', 'uncertainty', 'audio'):
            if not isinstance(getattr(self, name), str):
                raise ValueError('Description metadata must contain text values.')
        self.speech_seconds = seconds(self.speech_seconds)
        self.speed = float(self.speed)
        self.text = self.text.strip()
        if self.end <= self.start or not self.text:
            raise ValueError('Description needs text and an end after its start.')
        if duration and self.end > duration + 0.05:
            raise ValueError('Description extends past the video.')
        self.event_start = self.start if self.event_start is None else seconds(self.event_start)
        self.event_end = self.end if self.event_end is None else seconds(self.event_end)
        if self.event_end <= self.event_start or (duration and self.event_end > duration + .05):
            raise ValueError('Invalid visual event interval.')
        if self.disposition not in ('unplanned', 'in-gap', 'pause', 'unresolved'):
            raise ValueError('Invalid description disposition.')
        if not math.isfinite(self.speed) or not 1 <= self.speed <= 1.15:
            raise ValueError('Narration speed must be between 1 and 1.15.')
        return self


def response_json(data):
    if isinstance(data,str):return json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '',data.strip()))
    return data


def parse_cues(data, duration=0):
    data=response_json(data)
    if isinstance(data, dict):
        data = data.get('descriptions', data.get('cues', data.get('audio_descriptions', [])))
    if not isinstance(data, list):
        raise ValueError('Expected a JSON list of descriptions.')
    names = {f.name for f in fields(Cue)} - {'start', 'end', 'text'}
    return sorted([Cue(seconds(x.get('start',x.get('start_time_mmss'))), seconds(x.get('end',x.get('end_time_mmss'))), str(x.get('text',x.get('description_text',''))),
                       **{k: v for k, v in x.items() if k in names}).validate(duration)
                   for x in data], key=lambda c: c.start)


def normalize_generated(data,duration,log=lambda _:None):
    """Validate observations without deleting real recurrence or shifting events.

    Only identical rows of the same event are duplicates. Overlap is input to
    the shared placement engine, never a reason to invent a new event time.
    """
    data=response_json(data)
    rows=data.get('descriptions',data.get('audio_descriptions',data.get('cues',[]))) if isinstance(data,dict) else data
    if not isinstance(rows,list):raise ValueError('Expected a description list.')
    parsed=[]
    for row in rows:
        try:
            start=seconds(row.get('start',row.get('start_time_mmss')));end=seconds(row.get('end',row.get('end_time_mmss')))
            text=str(row.get('text',row.get('description_text',''))).strip()
            if not text:raise ValueError('Empty description.')
            if end <= start or start >= duration:raise ValueError('Invalid event interval.')
            end = min(duration,end)
            allowed = {f.name for f in fields(Cue)} - {'start','end','text'}
            cue = Cue(start,end,text,**{k:v for k,v in row.items() if k in allowed}).validate(duration)
            parsed.append(cue)
        except (ValueError,TypeError,AttributeError):log('Skipped a malformed generated description.')
    cues=[]
    seen=set()
    for cue in sorted(parsed,key=lambda c:c.start):
        key=(cue.event_id,cue.event_start,cue.event_end,cue.text)
        if key in seen:log('Removed a duplicate observation of the same event.');continue
        seen.add(key);cues.append(cue)
    return cues


def scene_data(data):
    data=response_json(data)
    if not isinstance(data,dict) or not isinstance(data.get('layout'),str) or not isinstance(data.get('objects'),list):raise ValueError('Invalid spatial scene response.')
    objects=[];used=set()
    for item in data['objects']:
        if not isinstance(item,dict) or not isinstance(item.get('name'),str) or not isinstance(item.get('description'),str):continue
        try:x,y=float(item['x']),float(item['y'])
        except (ValueError,TypeError,KeyError):continue
        if not math.isfinite(x) or not math.isfinite(y):continue
        point=(max(0,min(10,round(x))),max(0,min(10,round(y))))
        if point in used:
            free=[(i,j) for i in range(11) for j in range(11) if (i,j) not in used]
            if not free:break
            point=min(free,key=lambda p:(p[0]-x)**2+(p[1]-y)**2)
        used.add(point);objects.append(dict(item,x=point[0],y=point[1]))
    return dict(layout=data['layout'],objects=objects)


def import_subtitles(path, duration=0, warnings=None):
    b = Path(path).read_bytes()
    if b.startswith((b'\xff\xfe',b'\xfe\xff')):text=b.decode('utf-16')
    else:
        try:text=b.decode('utf-8-sig')
        except UnicodeDecodeError:text=b.decode('cp1252')
    pattern = r'(\d{1,2}:\d{2}:\d{2}[,.]\d{2,3})\s+-{1,2}>\s+(\d{1,2}:\d{2}:\d{2}[,.]\d{2,3})[^\n]*\n(.*?)(?=\n\s*\n|\Z)'
    cues=[]
    for a,b,t in re.findall(pattern,text.replace('\r',''),re.S):
        start,end=seconds(a),seconds(b);text=re.sub('<[^>]*>','',t).strip()
        if not text or end<=start:
            if warnings is not None:warnings.append(f'Skipped empty or zero-length subtitle at {a}.')
            continue
        cues.append(Cue(start,end,text).validate(duration))
    if not cues:
        raise ValueError('No timed subtitles found.')
    return sorted(cues, key=lambda c: c.start)


@dataclass
class Project:
    video: str = ''
    duration: float = 0
    cues: list[Cue] = field(default_factory=list)
    glossary: str = ''
    coverage: list[dict] = field(default_factory=list)
    analysis: dict = field(default_factory=dict)

    def save(self, path):
        from .engine.core import atomic_json
        atomic_json(path, {'version': 1, **asdict(self)})

    @classmethod
    def load(cls, path):
        j = json.loads(Path(path).read_text(encoding='utf-8-sig'))
        if j.get('version') != 1:
            raise ValueError('Unsupported project version.')
        return cls(j['video'], seconds(j['duration']), parse_cues(j['cues'], j['duration']), j.get('glossary', ''), j.get('coverage', []), j.get('analysis', {}))

    def export(self, path):
        if Path(path).suffix.lower() == '.srt':
            text = '\n\n'.join(f'{i}\n{stamp(c.start)} --> {stamp(c.end)}\n{c.text}' for i, c in enumerate(self.cues, 1)) + '\n'
        else:
            text = '\n'.join(c.text for c in self.cues) + '\n'
        Path(path).write_text(text, encoding='utf-8')
