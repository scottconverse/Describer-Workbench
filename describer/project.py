import json
import math
import re
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from uuid import uuid4


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
    timing_start: float | None = None
    timing_end: float | None = None
    audio_volume: float | None = None
    narration_text: str = ''
    cue_id: str = field(default_factory=lambda: uuid4().hex, compare=False)
    origin: str = 'legacy'
    manually_edited: bool = False
    review_status: str = 'unreviewed'
    review_history: list[dict] = field(default_factory=list)

    def narration_window(self):
        """Authored scheduling intent is separate from observed provenance."""
        return (self.timing_start, self.timing_end) if self.timing_start is not None else (self.event_start, self.event_end)

    def reviewed(self):
        from dataclasses import replace
        return replace(self, uncertainty='', disposition='unplanned', review_status='reviewed',
                       review_history=[*self.review_history, {'status':self.review_status, 'uncertainty':self.uncertainty,
                           'text':self.text, 'event_id':self.event_id, 'action':'human-checked'}])

    def edited(self, start, end, text, duration=0):
        """Keep observation/review identity while invalidating changed narration."""
        from dataclasses import replace
        candidate = replace(self, start=start, end=end, text=text).validate(duration)
        if (candidate.start, candidate.end) != (self.start, self.end):
            candidate.timing_start, candidate.timing_end = candidate.start, candidate.end
        if (candidate.start, candidate.end, candidate.text) != (self.start, self.end, self.text):
            candidate.manually_edited = True
            if self.review_status in ('reviewed', 'approved'):
                import hashlib
                candidate.review_history = [*self.review_history, {'status': self.review_status,
                    'text_sha256': hashlib.sha256(self.text.encode('utf-8')).hexdigest(), 'start': self.start, 'end': self.end}]
                candidate.review_status = 'needs-review'
            candidate.audio = ''
            candidate.speech_seconds = 0
            candidate.speed = 1
            candidate.audio_volume = None
            candidate.narration_text = ''
            candidate.disposition = 'unresolved' if self.disposition == 'unresolved' or self.uncertainty or candidate.review_status == 'needs-review' else 'unplanned'
        return candidate

    def validate(self, duration=0):
        self.start, self.end = seconds(self.start), seconds(self.end)
        for name in ('text', 'event_id', 'kind', 'evidence', 'uncertainty', 'audio','narration_text', 'cue_id', 'origin'):
            if not isinstance(getattr(self, name), str):
                raise ValueError('Description metadata must contain text values.')
        if not self.cue_id or self.review_status not in ('unreviewed', 'needs-review', 'reviewed', 'approved') or not isinstance(self.manually_edited, bool) or not isinstance(self.review_history, list):
            raise ValueError('Invalid description identity or review state.')
        self.speech_seconds = seconds(self.speech_seconds)
        self.speed = float(self.speed)
        if self.audio_volume is not None:
            self.audio_volume = float(self.audio_volume)
            if not math.isfinite(self.audio_volume) or not 0 < self.audio_volume <= 100:
                raise ValueError('Invalid recorded narration volume.')
        self.text = self.text.strip()
        if self.end <= self.start or not self.text:
            raise ValueError('Description needs text and an end after its start.')
        if duration and self.end > duration + 0.05:
            raise ValueError('Description extends past the video.')
        self.event_start = self.start if self.event_start is None else seconds(self.event_start)
        self.event_end = self.end if self.event_end is None else seconds(self.event_end)
        if self.event_end <= self.event_start or (duration and self.event_end > duration + .05):
            raise ValueError('Invalid visual event interval.')
        if (self.timing_start is None) != (self.timing_end is None):
            raise ValueError('Authored narration timing requires a start and end.')
        if self.timing_start is not None:
            self.timing_start, self.timing_end = seconds(self.timing_start), seconds(self.timing_end)
            if self.timing_end <= self.timing_start or (duration and self.timing_end > duration + .05):
                raise ValueError('Invalid authored narration interval.')
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


def normalize_generated(data,duration,log=lambda _:None,*,strict=False):
    """Validate observations without deleting real recurrence or shifting events.

    Only identical rows of the same event are duplicates. Overlap is input to
    the shared placement engine, never a reason to invent a new event time.
    """
    data=response_json(data)
    rows=data.get('descriptions',data.get('audio_descriptions',data.get('cues',[]))) if isinstance(data,dict) else data
    if not isinstance(rows,list):raise ValueError('Expected a description list.')
    parsed=[]
    for index,row in enumerate(rows,1):
        try:
            start=seconds(row.get('start',row.get('start_time_mmss')));end=seconds(row.get('end',row.get('end_time_mmss')))
            text=str(row.get('text',row.get('description_text',''))).strip()
            if not text:raise ValueError('Empty description.')
            if end <= start or start >= duration:raise ValueError('Invalid event interval.')
            end = min(duration,end)
            allowed = {f.name for f in fields(Cue)} - {'start','end','text'}
            cue = Cue(start,end,text,**{k:v for k,v in row.items() if k in allowed}).validate(duration)
            parsed.append(cue)
        except (ValueError,TypeError,AttributeError) as exc:
            if strict:
                raise ValueError(f'Malformed chunk observation {index}; retry the chunk. No partial chunk was accepted as complete.') from exc
            log('Skipped a malformed generated description.')
    cues=[]
    seen=set()
    for cue in sorted(parsed,key=lambda c:c.start):
        key=(cue.event_id,cue.event_start,cue.event_end,cue.text)
        if key in seen:log('Removed a duplicate observation of the same event.');continue
        seen.add(key);cues.append(cue)
    return cues


# Models write IDs in any case: man_1, Man_plaid, Woman_3.
INTERNAL_ID = re.compile(r'\b[a-z]+(?:_[a-z0-9]+)+\b', re.I)


def glossary_labels(glossary='', entries=()):
    """Map model identity labels (for example man_1) to speakable words."""
    labels = {}
    for line in str(glossary or '').splitlines():
        key, _, detail = line.partition(':')
        if INTERNAL_ID.fullmatch(key.strip()):
            labels[key.strip()] = {'name': '', 'description': detail.strip()}
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):continue
        key = str(entry.get('id') or '').strip()
        if not key:continue
        name = str(entry.get('name') or entry.get('character_name') or '').strip()
        if INTERNAL_ID.fullmatch(name):name = ''
        detail = str(entry.get('description') or entry.get('visual_description') or '').strip()
        labels[key] = {'name': name, 'description': detail}
    return labels


def _spoken_label(entry):
    if entry and entry.get('name'):return entry['name']
    detail = ' '.join(INTERNAL_ID.sub('', (entry or {}).get('description', '')).split()[:8]).rstrip('.,;:')
    if not detail:return 'a person'
    first = detail.split()[0].lower()
    return detail[0].lower()+detail[1:] if first in ('a', 'an', 'the', 'one', 'two', 'three') else 'a '+detail


def speakable(text, labels):
    """Replace internal labels. Return (text, meaningful).

    meaningful is False when nothing but replaced labels remains, so the cue
    is held for review instead of being spoken.
    """
    if not INTERNAL_ID.search(text):return text, True
    pattern = re.compile(r'\b(?:(?:the|a|an)\s+)?(' + INTERNAL_ID.pattern + r')', re.I)
    folded = {str(key).lower(): entry for key, entry in labels.items()}
    def replace(match):
        return _spoken_label(labels.get(match.group(1)) or folded.get(match.group(1).lower()))
    cleaned = ' '.join(pattern.sub(replace, text).split())
    rest = re.sub(r'[^\w]', '', pattern.sub('', text))
    if cleaned:cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned, bool(rest)


def normalize_chunk(data, start, length, log=lambda _:None):
    """Reconcile clip-relative and unambiguous source-absolute model times.

    A malformed/mixed chunk must be retried, not counted as a complete job
    after silently losing its rows. Observation provenance is created only
    after these provider-produced times have been reconciled.
    """
    import copy
    data = response_json(data)
    if isinstance(data, dict) and not any(key in data for key in ('descriptions', 'audio_descriptions', 'cues')):
        # A reply with only a glossary is a failed chunk, not "nothing happened".
        raise ValueError('Malformed chunk output; retry the chunk. The reply had no descriptions list.')
    rows = data.get('descriptions', data.get('audio_descriptions', data.get('cues', []))) if isinstance(data, dict) else data
    if not isinstance(rows, list):raise ValueError('Expected a description list.')
    if not rows:return []
    values = []
    for row in rows:
        try:
            a = seconds(row.get('start', row.get('start_time_mmss')))
            b = seconds(row.get('end', row.get('end_time_mmss')))
            if b <= a or not isinstance(row.get('text', row.get('description_text')), str) or not row.get('text', row.get('description_text', '')).strip():
                raise ValueError('Invalid description')
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError('Malformed chunk output; retry the chunk. No partial chunk was accepted as complete.') from exc
        values.append((a, b))
    # Only the event start must fall inside the chunk. An end that runs past
    # a short (final) chunk is clamped to the chunk end, not rejected.
    relative = all(0 <= a < length for a,b in values)
    absolute = start > 0 and all(start <= a < start + length for a,b in values)
    reference = data.get('timestamp_reference') if isinstance(data, dict) else None
    if reference == 'clip':absolute = False
    elif reference == 'source':relative = False
    if relative and absolute:
        raise ValueError('Ambiguous chunk timestamps; retry with timestamp_reference="clip" or "source". No partial result was accepted.')
    if not relative and not absolute:
        raise ValueError('Mixed or out-of-range chunk timestamps; retry the chunk. No partial result was accepted.')
    adjusted = []
    for row,(a,b) in zip(rows, values):
        row = copy.deepcopy(row)
        row['start'],row['end'] = (a-start,min(b,start+length)-start) if absolute else (a,min(b,length))
        # Observation metadata comes from the normalized response, not arbitrary
        # provider-supplied scheduling/audio fields.
        for key in ('event_start','event_end','audio','speech_seconds','speed','audio_volume','timing_start','timing_end','narration_text', 'cue_id', 'origin', 'manually_edited', 'review_status', 'review_history'):
            row.pop(key, None)
        row['origin'] = 'generated'
        adjusted.append(row)
    if absolute:log('Reconciled source-absolute chunk timestamps.')
    return normalize_generated(adjusted,length,log,strict=True)


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
    timestamp = r'(?:\d+:)?\d{2}:\d{2}[,.]\d{2,3}'
    pattern = rf'^({timestamp})\s+-{{1,2}}>\s+({timestamp})[^\n]*\n(.*?)(?=\n\s*\n|\Z)'
    cues=[]
    for a,b,t in re.findall(pattern,text.replace('\r',''),re.S|re.M):
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
        if len({cue.cue_id for cue in self.cues}) != len(self.cues):
            raise ValueError('Duplicate description identity; the existing project file was not changed.')
        # Older applications discard unknown cue fields when re-saving v1.
        # Require a reader that understands preservation/review metadata.
        atomic_json(path, {'version': 2, **asdict(self)})

    @classmethod
    def load(cls, path):
        j = json.loads(Path(path).read_text(encoding='utf-8-sig'))
        if j.get('version') not in (1, 2):
            raise ValueError('Unsupported project version.')
        cues = parse_cues(j['cues'], j['duration'])
        if len({cue.cue_id for cue in cues}) != len(cues):raise ValueError('Duplicate description identity in saved project.')
        return cls(j['video'], seconds(j['duration']), cues, j.get('glossary', ''), j.get('coverage', []), j.get('analysis', {}))

    def export(self, path):
        if Path(path).suffix.lower() == '.srt':
            text = '\n\n'.join(f'{i}\n{stamp(c.start)} --> {stamp(c.end)}\n{c.text}' for i, c in enumerate(self.cues, 1)) + '\n'
        else:
            text = '\n'.join(c.text for c in self.cues) + '\n'
        Path(path).write_text(text, encoding='utf-8')
