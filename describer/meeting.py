"""Public meeting mode: describe what changes, not every sampled frame (F1).

Other genres keep the default behavior. Only `drafting_mode = "Public meeting"`
turns on the change gate, the prior-cue prompt and the repeat merge.
"""
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


def prior_instruction(texts):
    texts = [t for t in texts if t][-PRIOR_CUES:]
    rule = ('This is a public meeting. Describe only what is new since the previous descriptions. '
            'If nothing new is visible, return an empty descriptions list: {"descriptions":[]}. ')
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


def merge_repeats(cues, log=lambda _: None, labels=()):
    """Remove cues that say again what a recent cue said.

    `cues` are dicts sorted by event start. A repeat of the cue just before
    is joined to it (the kept cue spans both events). A repeat of an earlier
    cue from the last MERGE_WINDOW seconds is dropped. "Still" restatements
    are dropped the same way.
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
    if counts['merged'] or counts['dropped']:
        log(f"Public meeting mode: merged {counts['merged']} repeated and dropped {counts['dropped']} restating descriptions.")
    return out
