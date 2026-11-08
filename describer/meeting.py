"""Public meeting mode: describe what changes, not every sampled frame (F1).

Other genres keep the default behavior. Only `drafting_mode = "Public meeting"`
turns on the change gate, the prior-cue prompt and the repeat merge.
"""
import html
import re

MODE = 'Public meeting'
MODES = ('', MODE)

# A frame is "changed" when the whole picture moves a little, one area of it
# moves a lot, or enough pixels change sharply. Values are 0..255 grey.
# The sharp-pixel rule finds a new slide that uses the same template as the
# old one: only thin text changes, so area averages stay small. Measured on
# real slides: a text-only change moves 1-11 % of pixels by more than 40;
# the same slide 2 s later moves 0-0.1 %.
THUMB_W, THUMB_H = 256, 144
GRID_X, GRID_Y = 8, 4
WHOLE_DIFF = 6.0
CELL_DIFF = 24.0
SHARP_DIFF = 40
SHARP_SHARE = .004

PRIOR_CUES = 3
MERGE_SIMILARITY = .8
RESTATE_SIMILARITY = .5
# A repeat of any cue from the last 3 minutes is removed, not only the cue just before.
MERGE_WINDOW = 180
RESTATE_WORDS = re.compile(r'\b(remains?|remaining|continues?|continuing|still)\b', re.I)
_ARTICLES = {'a', 'an', 'the'}
_TOKEN = re.compile(r"[a-z0-9']+")


def enabled(settings):
    return (settings or {}).get('drafting_mode', '') == MODE


# Slides on a wall screen need more pixels than 640 to be read (F4).
FRAME_SIDE = 1280


def frame_side(settings):
    return FRAME_SIDE if enabled(settings) else 640


def thumbnails(paths, cancel=None):
    """Small grey thumbnails of image files, one bytes object per file."""
    from .services import run, tool
    if not paths:
        return []
    args = [tool('ffmpeg'), '-v', 'error']
    for path in paths:
        args += ['-i', str(path)]
    graph = ';'.join(f'[{i}:v]scale={THUMB_W}:{THUMB_H},format=gray[g{i}]' for i in range(len(paths)))
    graph += ';' + ''.join(f'[g{i}]' for i in range(len(paths))) + f'concat=n={len(paths)}:v=1:a=0[out]'
    raw = run(args + ['-filter_complex', graph, '-map', '[out]', '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], cancel)
    size = THUMB_W * THUMB_H
    if len(raw) != size * len(paths):
        raise ValueError('Could not measure frame changes.')
    return [raw[i * size:(i + 1) * size] for i in range(len(paths))]


def changed(a, b):
    """True when thumbnail b shows a visible change from thumbnail a."""
    if a is None:
        return True
    diffs = [abs(x - y) for x, y in zip(a, b)]
    if sum(diffs) / len(a) > WHOLE_DIFF:
        return True
    if sum(d > SHARP_DIFF for d in diffs) >= SHARP_SHARE * len(a):
        return True
    cw, ch = THUMB_W // GRID_X, THUMB_H // GRID_Y
    for gy in range(GRID_Y):
        for gx in range(GRID_X):
            diff = 0
            for y in range(gy * ch, (gy + 1) * ch):
                row = y * THUMB_W
                for x in range(gx * cw, (gx + 1) * cw):
                    diff += abs(a[row + x] - b[row + x])
            if diff / (cw * ch) > CELL_DIFF:
                return True
    return False


class ChangeGate:
    """Keeps only frames that differ from the last frame the model saw."""

    def __init__(self, measure=None):
        self.measure = measure
        self.last = None
        self.sent = 0
        self.skipped = 0

    def __call__(self, frames, cancel=None):
        thumbs = (self.measure or thumbnails)([path for path, _ in frames], cancel)
        kept = []
        for frame, thumb in zip(frames, thumbs):
            if changed(self.last, thumb):
                kept.append(frame)
                self.last = thumb
        self.sent += len(kept)
        self.skipped += len(frames) - len(kept)
        return kept


# F2: a 2 s event has no room for a 3 s line. In meeting mode a line may use
# a pause up to this many seconds from its event.
NARRATION_REACH = 5.0


def narration_reach(settings):
    return NARRATION_REACH if enabled(settings) else 0.0


def transcript(captions):
    """(start, end, line) rows from caption cues, each spoken line once.

    Rolling captions (YouTube) show the last line again in the next cue.
    """
    rows, last = [], ''
    for cue in captions:
        for line in (html.unescape(part).strip() for part in cue.text.splitlines()):
            if line and line != last:
                rows.append((cue.start, cue.end, line))
                last = line
    return rows


def transcript_instruction(rows, start, length):
    said = [f'[{max(0.0, a - start):.1f}] {text}' for a, b, text in rows if b > start and a < start + length]
    if not said:
        return ''
    return ('Transcript of what is said aloud in this clip, with clip times: ' + ' '.join(said) + ' (end of transcript). '
            'Do not describe anything the speakers say aloud; describe only what a listener cannot learn from the audio. ')


def event_instruction(prompt=''):
    """F3: typed meeting events and the gender rule, once per prompt."""
    from .catalogue import PROMPTS
    rules = PROMPTS[MODE]
    short = ('Also give "short_text": the same main fact in at most 4 words, '
             'for a short pause in the speech. ')
    return short if rules in (prompt or '') else rules + ' ' + short


# F2: pauses come from word timings, not whole caption lines. A caption line
# often holds a long silence between two words.
WORD_TIME = re.compile(r'<(\d+:\d\d:\d\d\.\d+)>')
CUE_TIME = re.compile(r'(\d+:\d\d:\d\d\.\d+)\s+-->\s+(\d+:\d\d:\d\d\.\d+)')
WORD_LONGEST = .7  # a word lasts at most this long; the rest is silence
WORD_PAD = .1


def _clock(value):
    h, m, s = value.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def word_spans(path, duration):
    """Speech spans from a VTT file with word times (<00:00:01.200> tags).

    Returns None when the file has no word times; the caller then protects
    each whole caption line, as before. A plain line that is not a repeat of
    a recent line (rolling captions) protects its whole caption span.
    """
    from pathlib import Path
    text = Path(path).read_text(encoding='utf-8-sig', errors='replace')
    if not WORD_TIME.search(text):
        return None
    spans, recent = [], []
    for block in re.split(r'\n\s*\n', text.replace('\r\n', '\n')):
        lines = block.strip().split('\n')
        timing = next((i for i, line in enumerate(lines) if CUE_TIME.search(line)), None)
        if timing is None:
            continue
        a, b = (_clock(v) for v in CUE_TIME.search(lines[timing]).groups())
        for line in lines[timing + 1:]:
            plain = ' '.join(re.sub(r'<[^>]*>', '', line).split())
            if not plain:
                continue
            if not WORD_TIME.search(line):
                if plain not in recent:
                    spans.append([max(0.0, a - WORD_PAD), min(duration, b + WORD_PAD)])
            else:
                parts = WORD_TIME.split(line)
                times = ([a] if re.sub(r'<[^>]*>', '', parts[0]).strip() else []) + [_clock(t) for t in parts[1::2]]
                for i, t in enumerate(times):
                    following = times[i + 1] if i + 1 < len(times) else b
                    end = min(max(t, following), t + WORD_LONGEST)
                    spans.append([max(0.0, t - WORD_PAD), min(duration, end + WORD_PAD)])
            recent = (recent + [plain])[-3:]
    return spans


# F2: pause budget. Only the most important pause cues may stop the video.
PAUSE_BUDGET = 8.0
PRIORITY = {'vote': 0, 'speaker_change': 1, 'slide': 2, 'on_screen_text': 2, 'scene_change': 3}


def pause_budget(settings):
    """Seconds of pause narration allowed per minute of video, or None (no limit)."""
    if not enabled(settings):
        return None
    value = (settings or {}).get('max_pause_seconds_per_minute', PAUSE_BUDGET)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value < float('inf'):
        raise ValueError('max_pause_seconds_per_minute must be a number of 0 or more.')
    return float(value)


def apply_pause_budget(cues, coverage, budget, log=lambda _: None):
    """Drop pause cues over the budget in each minute, least important first.

    Votes always keep their pause. A dropped cue gets disposition
    "dropped_no_gap" and is listed in coverage; it is never spoken.
    """
    rows = {row.get('cue_id'): row for row in coverage if row.get('cue_id')}
    minutes = {}
    for cue in cues:
        if cue.disposition == 'pause':
            minutes.setdefault(int(cue.start // 60), []).append(cue)
    dropped = 0
    for group in minutes.values():
        used = 0.0
        for cue in sorted(group, key=lambda c: (PRIORITY.get(c.kind, len(PRIORITY)), c.start)):
            if cue.kind == 'vote' or used + cue.speech_seconds <= budget + 1e-6:
                used += cue.speech_seconds
                continue
            cue.disposition = 'dropped_no_gap'
            dropped += 1
            if cue.cue_id in rows:
                rows[cue.cue_id].update(disposition='dropped_no_gap',
                    reason=f'No speech-free gap, and over the pause budget of {budget:g} s per minute.')
    if dropped:
        log(f'Public meeting mode: {dropped} descriptions had no gap and were over the pause budget; they are listed in coverage, not spoken.')


# F3: the transcript says when a vote happens; a 1 s frame pass says who and how many.
VOTE_WORDS = re.compile(r"\b(all (those )?in favou?r|ayes?|motion (carries|passes|passed|fails|failed)|opposed|roll call)\b", re.IGNORECASE)
VOTE_LEAD = 1.0
VOTE_SPAN = 8.0  # 8 frames at 1 s: the frame sampler sends at most 8 frames


def vote_windows(rows, start, stop):
    """(window start, length, lines) for each vote in [start, stop), in video time."""
    windows = []
    for a, _, text in rows:
        if not (start <= a < stop) or not VOTE_WORDS.search(text):
            continue
        if windows and a < windows[-1][0] + windows[-1][1]:
            windows[-1][2].append(text)
            continue
        w0 = max(start, a - VOTE_LEAD)
        windows.append((w0, min(stop, w0 + VOTE_SPAN) - w0, [text]))
    return [w for w in windows if w[1] >= 1]


def vote_instruction(lines, length):
    return ('Question: is anyone raising a hand to vote? The transcript says a vote happens in this clip: "'
            + ' '.join(lines) + '". Look at every frame. Count the people with a raised hand in the frame where the most hands are up. '
            'Say "members" or "people", never a gender. '
            'Return JSON {"timestamp_reference":"clip","descriptions":[{"start":0.0,"end":2.0,"text":"<N> members raise their hands","kind":"vote"}]} '
            f'with numeric clip times that fit within this {length:.2f}-second clip. '
            'If no hand is raised, return {"timestamp_reference":"clip","descriptions":[]}.')


def prior_instruction(texts):
    texts = [t for t in texts if t][-PRIOR_CUES:]
    rule = ('This is a public meeting. Describe only what is new since the previous descriptions. '
            'If nothing new is visible, return an empty descriptions list: {"descriptions":[]}. '
            'When a new slide or screen with text appears, give its exact title word for word in quotes, '
            'then its main point in a few words. ')
    if texts:
        rule += 'Previous descriptions, oldest first: ' + ' | '.join(texts) + '. '
    return rule


def tokens(text, labels=()):
    words = _TOKEN.findall(str(text).lower())
    drop = _ARTICLES | {str(label).lower() for label in labels}
    return {w for w in words if w not in drop and not re.fullmatch(r'[a-z]+(_[a-z0-9]+)+', w)}


def similarity(a, b, labels=()):
    ta, tb = tokens(a, labels), tokens(b, labels)
    if not ta and not tb:
        return 1.0
    return len(ta & tb) / len(ta | tb)


def _repeats(prev, cue, labels):
    if prev.get('manually_edited') or cue.get('manually_edited'):
        return None
    score = similarity(prev['text'], cue['text'], labels)
    if score >= MERGE_SIMILARITY:
        return 'merged'
    if RESTATE_WORDS.search(cue['text']) and score >= RESTATE_SIMILARITY:
        return 'dropped'
    return None


def merge_repeats(cues, log=lambda _: None, labels=(), dropped=None):
    """Remove cues that say again what a recent cue said.

    `cues` are dicts sorted by event start. A repeat of the cue just before
    is joined to it (the kept cue spans both events). A repeat of an earlier
    cue from the last MERGE_WINDOW seconds is dropped. "Still" restatements
    are dropped the same way. Each dropped span is added to `dropped`, so
    coverage can flag it instead of leaving a silent hole.
    """
    out = []
    counts = {'merged': 0, 'dropped': 0}
    for cue in cues:
        recent = [c for c in out if cue['start'] - c['start'] <= MERGE_WINDOW]
        kind = next((k for k in (_repeats(c, cue, labels) for c in reversed(recent)) if k), None)
        if kind is None:
            out.append(cue)
            continue
        counts[kind] += 1
        prev = out[-1]
        if _repeats(prev, cue, labels):
            prev['end'] = max(prev['end'], cue['end'])
            prev['event_end'] = max(prev.get('event_end', prev['end']), cue.get('event_end', cue['end']))
        elif dropped is not None:
            dropped.append({'start': cue.get('event_start', cue['start']), 'end': cue.get('event_end', cue['end']),
                            'reason': 'No new change: the model repeated an earlier description, so it was not said again.'})
    if counts['merged'] or counts['dropped']:
        log(f"Public meeting mode: merged {counts['merged']} repeated and dropped {counts['dropped']} restating descriptions.")
    return out
