"""Preservation and transactional drafting regressions, including real Qt widgets."""
import copy
from dataclasses import asdict

import pytest

from describer.project import Cue, Project


def test_range_keeps_outside_authored_reviewed_and_boundary_cues():
    from describer.drafting import DraftProposal
    old = Project('source', 120, [Cue(1, 4, 'Outside.'), Cue(19, 22, 'Crosses boundary.'), Cue(25, 28, 'Human correction.')], 'Ada: blue coat')
    original = copy.deepcopy(old)
    draft = Project('source', 120, [Cue(25, 27, 'Different proposal.'), Cue(35, 37, 'New observation.')], 'Ada: red coat')
    proposal = DraftProposal(old, draft, 20, 40)
    merged = proposal.apply(old, {draft.cues[1].cue_id}, set(), False)
    assert merged.cues[:3] == original.cues
    assert merged.glossary == original.glossary
    assert asdict(old) == asdict(original)
    with pytest.raises(ValueError, match='explicit'):
        proposal.apply(old, {draft.cues[0].cue_id}, set(), False)
    with pytest.raises(ValueError, match='boundary'):
        proposal.apply(old, set(), {old.cues[1].cue_id}, False)


def test_draft_rejects_stale_project_and_maintains_full_undo(qt_application_lifetime, tmp_path):
    from describer.app import Window
    from describer.drafting import DraftProposal, ProjectChange
    old = Project('source', 100, [Cue(22, 24, 'Checked.', event_id='observed', review_status='approved')], 'Old glossary', [{'event_id': 'observed', 'text': 'Checked.'}], {'usage': [{'operation': 'describe', 'total_tokens': 3}]})
    draft = Project('source', 100, [Cue(22, 24, 'Proposed.', event_id='new')], 'New glossary', [{'event_id': 'new', 'text': 'Proposed.'}], {'usage': old.analysis['usage']+[{'total_tokens': 5}]})
    proposal = DraftProposal(old, draft, 20, 40)
    after = proposal.apply(old, {draft.cues[0].cue_id}, {old.cues[0].cue_id}, True)
    assert after.cues[0].review_status != 'approved'
    assert after.glossary == 'New glossary'
    assert after.coverage[0]['event_id'] == 'new'
    changed = copy.deepcopy(old)
    changed.glossary = 'User changed glossary during analysis'
    with pytest.raises(ValueError, match='changed'):
        proposal.apply(changed, set(), set(), False)
    window = Window(tmp_path/'settings.json')
    try:
        window.project = old
        window.refresh()
        window.undo_stack.push(ProjectChange(window, old, after, 'Apply draft'))
        assert asdict(window.project) == asdict(after)
        path = tmp_path/'project.adproject'
        window.project.save(path)
        assert asdict(Project.load(path)) == asdict(after)
        window.undo_stack.undo()
        assert asdict(window.project) == asdict(old)
        window.undo_stack.redo()
        assert asdict(window.project) == asdict(after)
    finally:
        window.dirty = False
        window.close()


def test_approval_is_not_carried_to_changed_text_or_assigned_by_provider():
    from describer.project import normalize_chunk
    cue = Cue(1, 3, 'Approved observation.', review_status='approved').validate(10)
    edited = cue.edited(1, 3, 'Changed observation.', 10)
    assert edited.cue_id == cue.cue_id and edited.manually_edited
    assert edited.review_status == 'needs-review' and edited.review_history
    generated = normalize_chunk({'descriptions': [{'start': 1, 'end': 3, 'text': 'AI observation.', 'review_status': 'approved', 'cue_id': cue.cue_id}]}, 0, 10)[0]
    assert generated.review_status == 'unreviewed' and generated.cue_id != cue.cue_id


def test_real_dialog_cancel_and_explicit_replacement(qt_application_lifetime, tmp_path):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QCheckBox, QDialogButtonBox
    from describer.app import Window
    from describer.drafting import DraftProposal, review_proposal
    window = Window(tmp_path/'settings.json')
    try:
        window.project = Project('fixture', 60, [Cue(21, 23, 'Human observation.', review_status='reviewed')])
        original = asdict(window.project)
        proposal = DraftProposal(window.project, Project('fixture', 60, [Cue(21, 23, 'AI proposal.')]), 20, 40)
        QTimer.singleShot(0, lambda: QApplication.activeModalWidget().reject())
        assert review_proposal(window, proposal) is None
        assert asdict(window.project) == original
        seen = []
        def operate():
            dialog = QApplication.activeModalWidget()
            boxes = dialog.findChildren(QCheckBox)
            existing = next(b for b in boxes if b.text().startswith('Replace existing'))
            proposed = next(b for b in boxes if b.text().startswith('Use proposed'))
            seen.append(not existing.isChecked() and not proposed.isChecked())
            proposed.click()
            buttons = dialog.findChild(QDialogButtonBox)
            buttons.button(QDialogButtonBox.Apply).click()
            seen.append(dialog.isVisible())  # Missing explicit replacement is blocked.
            existing.click()
            buttons.button(QDialogButtonBox.Apply).click()
        QTimer.singleShot(0, operate)
        result = review_proposal(window, proposal)
        assert seen == [True, True]
        assert result.cues[0].text == 'AI proposal.' and asdict(window.project) == original
    finally:
        window.dirty = False
        window.close()


def test_invalid_identity_cannot_overwrite_saved_work(tmp_path):
    path = tmp_path/'saved.adproject'
    cue = Cue(1, 3, 'Original.').validate(10)
    project = Project('source', 10, [cue])
    project.save(path)
    original = path.read_bytes()
    project.cues.append(copy.deepcopy(cue))
    with pytest.raises(ValueError, match='identity'):project.save(path)
    assert path.read_bytes() == original


def test_legacy_projects_load_but_new_saves_require_a_metadata_aware_reader(tmp_path):
    import json
    path = tmp_path/'legacy.adproject'
    legacy = {'version':1,'video':'source','duration':10,'cues':[{'start':1,'end':3,'text':'Existing work.'}],'glossary':'Existing glossary'}
    path.write_text(json.dumps(legacy))
    project = Project.load(path)
    assert project.cues[0].origin == 'legacy' and project.glossary == legacy['glossary']
    saved = tmp_path/'candidate.adproject'
    project.save(saved)
    assert json.loads(saved.read_text())['version'] == 2
    assert asdict(Project.load(saved)) == asdict(project)
    assert json.loads(path.read_text()) == legacy


def test_partial_narration_placement_is_not_reused_outside_the_event_range():
    from describer.drafting import DraftProposal
    old = Project('source',60,[Cue(40,44,'Outside narration.').validate(60)])
    scheduled = Cue(40,43,'Observation from this range.',event_start=25,event_end=28,disposition='in-gap').validate(60)
    draft = Project('source',60,[scheduled])
    proposal = DraftProposal(old,draft,20,40)
    merged = proposal.apply(old,{scheduled.cue_id},set())
    assert (merged.cues[0].start,merged.cues[0].end,merged.cues[0].disposition) == (25,28,'unplanned')
    assert asdict(merged.cues[1]) == asdict(old.cues[0])


def test_review_history_and_coverage_survive_service_edit(tmp_path):
    from contextlib import closing
    from describer.engine.service import DescriptionService
    source = tmp_path/'source.mp4'
    source.write_bytes(b'fixture for text-only export; no media inference')
    cue = Cue(1, 3, 'Approved.',event_id='source-event',evidence='Original visual evidence',review_status='approved').validate(10)
    with closing(DescriptionService(tmp_path/'engine')) as service:
        job = service.submit(project=Project(str(source),10,[cue],analysis={'usage':[{'total_tokens':5}]}),operation='export',export_format='txt')
        before = service.wait(job['id'])
        service.edit(job['id'],service.get_job(job['id'])['revision'],cues=[dict(asdict(cue),text='Human correction.')])
        after = service.result(job['id'])
        assert after.cues[0].cue_id == before.cues[0].cue_id
        assert after.cues[0].review_status == 'needs-review'
        assert after.cues[0].review_history
        assert after.coverage[0]['cue_id'] == cue.cue_id
        assert after.coverage[0]['text'] == 'Human correction.'
        assert after.analysis['usage'] == [{'total_tokens':5}]
