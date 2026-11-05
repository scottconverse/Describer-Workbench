"""Explicit, reversible draft proposals. No generated output silently edits work."""
import copy
from dataclasses import asdict
import hashlib
import json

def fingerprint(project):
    return hashlib.sha256(json.dumps(asdict(project), sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def bounds(cue):
    return min(cue.start, cue.event_start if cue.event_start is not None else cue.start), max(cue.end, cue.event_end if cue.event_end is not None else cue.end)


def overlaps(a, b):
    left, right = bounds(a)
    start, end = bounds(b)
    return left < end and start < right


def coverage_for(cues, rows, previous=()):
    """Keep unchanged rows verbatim; refresh edited facts without erasing evidence."""
    output = []
    before = {c.cue_id: c for c in previous}
    by_id, by_event = {}, {}
    for row in rows:
        if row.get('cue_id'):by_id.setdefault(row['cue_id'], []).append(row)
        if row.get('event_id'):by_event.setdefault(row['event_id'], []).append(row)
    for cue in cues:
        matches = by_id.get(cue.cue_id, [])
        if not matches and cue.event_id:
            matches = by_event.get(cue.event_id, [])
        row = copy.deepcopy(matches[0]) if len(matches) == 1 else {}
        if not row or cue.cue_id not in before or before[cue.cue_id] != cue:
            row.update({k: v for k, v in asdict(cue).items() if k not in ('audio', 'review_history')})
            row['reason'] = cue.uncertainty or ('Edited; re-plan narration.' if cue.disposition == 'unplanned' else row.get('reason', ''))
        output.append(row)
    return output


class DraftProposal:
    def __init__(self, current, generated, start, end):
        if current.video != generated.video or current.duration != generated.duration or not 0 <= start < end <= current.duration:
            raise ValueError('Draft source or range does not match the current project.')
        self.base = fingerprint(current)
        self.original = copy.deepcopy(current)
        self.generated = copy.deepcopy(generated)
        self.start, self.end = start, end
        self.existing = {c.cue_id: c for c in self.original.cues}
        self.candidates = {c.cue_id: c for c in self.generated.cues}
        if len(self.existing) != len(current.cues) or len(self.candidates) != len(generated.cues) or set(self.existing) & set(self.candidates):
            raise ValueError('Duplicate description identity in draft.')
        for cue in self.generated.cues:
            cue.validate(current.duration)
            if cue.event_start < start-.05 or cue.event_end > end+.05:
                raise ValueError('Proposed observation extends outside the requested range.')
            # Partial-job narration placement did not consider retained cues.
            cue.start, cue.end = cue.narration_window()
        self.conflicts = {key: {old.cue_id for old in current.cues if overlaps(cue, old)} for key, cue in self.candidates.items()}

    def replaceable(self, cue):
        a, b = bounds(cue)
        return self.start <= a and b <= self.end

    def apply(self, current, accepted, replaced, use_glossary=False):
        if fingerprint(current) != self.base:
            raise ValueError('The project changed while drafting; review a new proposal.')
        accepted, replaced = set(accepted), set(replaced)
        if not accepted <= self.candidates.keys() or not replaced <= self.existing.keys():
            raise ValueError('Unknown description identity in proposal.')
        if any(not self.replaceable(self.existing[key]) for key in replaced):
            raise ValueError('A description crossing a range boundary must be retained.')
        required = set().union(*(self.conflicts[key] for key in accepted)) if accepted else set()
        if required != replaced:
            raise ValueError('Each conflicting replacement needs an explicit choice and an accepted proposal.')
        result = copy.deepcopy(current)
        added = [copy.deepcopy(c) for c in self.generated.cues if c.cue_id in accepted]
        for cue in added:
            # Partial-range planning has not considered retained descriptions.
            cue.audio, cue.speech_seconds, cue.audio_volume, cue.narration_text = '', 0, None, ''
            cue.speed = 1
            cue.disposition = 'unresolved' if cue.uncertainty or cue.disposition == 'unresolved' else 'unplanned'
            cue.review_status, cue.review_history, cue.manually_edited, cue.origin = 'unreviewed', [], False, 'generated'
        result.cues = sorted([c for c in result.cues if c.cue_id not in replaced]+added, key=lambda c: c.start)
        retained = [c for c in current.cues if c.cue_id not in replaced]
        result.coverage = coverage_for(retained, current.coverage, current.cues)+coverage_for(added, self.generated.coverage)
        if use_glossary:result.glossary = self.generated.glossary
        result.analysis = copy.deepcopy(current.analysis)
        # Generation already includes previous usage. Keep its full ledger once.
        if 'usage' in self.generated.analysis:
            existing_usage = current.analysis.get('usage', [])
            generated_usage = self.generated.analysis['usage']
            common = 0
            for old, new in zip(existing_usage, generated_usage):
                if old != new:break
                common += 1
            result.analysis['usage'] = copy.deepcopy(existing_usage+generated_usage[common:])
        history = result.analysis.setdefault('draft_history', [])
        history.append({'range': [self.start, self.end], 'accepted': sorted(accepted), 'replaced': sorted(replaced),
                        'replaced_cues': [asdict(c) for c in current.cues if c.cue_id in replaced],
                        'replaced_coverage': [r for r in current.coverage if r.get('cue_id') in replaced or any(r.get('event_id') == self.existing[k].event_id for k in replaced)],
                        'glossary_changed': bool(use_glossary), 'previous_glossary': current.glossary if use_glossary else None,
                        'generation_analysis': copy.deepcopy({k:v for k,v in self.generated.analysis.items() if k != 'draft_history'})})
        result.analysis['requires_replan'] = True
        return result


# Imported only by desktop clients; the proposal/coverage helpers remain Qt-free.
def project_change_class():
    from PySide6.QtGui import QUndoCommand
    class ProjectChange(QUndoCommand):
        def __init__(self, window, before, after, title):
            super().__init__(title)
            self.window, self.before, self.after = window, copy.deepcopy(before), copy.deepcopy(after)
        def apply(self, project):
            self.window.project = copy.deepcopy(project)
            self.window._selected_cue = None
            self.window.dirty = True
            self.window.last_spoken = None
            self.window.played_pauses.clear()
            self.window.refresh()
            if project.cues:self.window.choose(0)
        def undo(self):self.apply(self.before)
        def redo(self):self.apply(self.after)
    return ProjectChange


def __getattr__(name):
    if name == 'ProjectChange':return project_change_class()
    raise AttributeError(name)


def review_proposal(window, proposal):
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QScrollArea, QWidget, QCheckBox, QPlainTextEdit, QDialogButtonBox
    from .desktop import clock
    dialog = QDialog(window)
    dialog.setWindowTitle('Review draft — your existing work is kept by default')
    dialog.resize(780, 700)
    layout = QVBoxLayout(dialog)
    introduction = QLabel('Choose proposed descriptions to use. Existing descriptions stay unless you explicitly select their replacement. Boundary-crossing descriptions always stay. Changes apply together and can be undone.')
    introduction.setWordWrap(True)
    layout.addWidget(introduction)
    area = QScrollArea()
    area.setWidgetResizable(True)
    host = QWidget()
    items = QVBoxLayout(host)
    area.setWidget(host)
    layout.addWidget(area)
    replacements, additions = {}, {}
    items.addWidget(QLabel('Existing descriptions that conflict with this draft'))
    conflicts = set().union(*proposal.conflicts.values()) if proposal.conflicts else set()
    for cue in proposal.original.cues:
        if cue.cue_id not in conflicts:continue
        field = QCheckBox(f'Replace existing {clock(cue.start)} — {cue.text} ({cue.review_status})')
        field.setEnabled(proposal.replaceable(cue))
        if not field.isEnabled():field.setToolTip('Crosses the requested range boundary; retained in full.')
        replacements[cue.cue_id] = field
        items.addWidget(field)
    items.addWidget(QLabel('Proposed descriptions'))
    for cue in proposal.generated.cues:
        field = QCheckBox(f'Use proposed {clock(cue.event_start)} — {cue.text}')
        field.setChecked(not proposal.conflicts[cue.cue_id])
        additions[cue.cue_id] = field
        items.addWidget(field)
    glossary = QCheckBox('Use the proposed glossary instead of my existing glossary')
    glossary.setEnabled(proposal.original.glossary != proposal.generated.glossary)
    items.addWidget(glossary)
    if glossary.isEnabled():
        preview = QPlainTextEdit('EXISTING GLOSSARY\n'+proposal.original.glossary+'\n\nPROPOSED GLOSSARY\n'+proposal.generated.glossary)
        preview.setReadOnly(True)
        preview.setAccessibleName('Existing and proposed glossary comparison')
        items.addWidget(preview)
    error = QLabel()
    error.setWordWrap(True)
    layout.addWidget(error)
    buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Apply)
    buttons.rejected.connect(dialog.reject)
    result = []
    def apply():
        try:
            accepted = {key for key, field in additions.items() if field.isChecked()}
            replaced = {key for key, field in replacements.items() if field.isChecked()}
            if not accepted and not replaced and not glossary.isChecked():
                dialog.reject()
                return
            result.append(proposal.apply(window.project, accepted, replaced, glossary.isChecked()))
            dialog.accept()
        except ValueError as exc:error.setText(str(exc))
    buttons.button(QDialogButtonBox.Apply).clicked.connect(apply)
    layout.addWidget(buttons)
    dialog.exec()
    return result[0] if result else None
