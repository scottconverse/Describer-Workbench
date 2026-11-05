"""Cue identity owns editor selection independently of presentation widgets."""
from collections.abc import Sequence
from dataclasses import dataclass

from .project import Cue


@dataclass
class CueSelection:
    cue_id: str | None = None
    position: int = -1

    def index(self, cues: Sequence[Cue]) -> int:
        return next((i for i,cue in enumerate(cues) if cue.cue_id==self.cue_id),-1)

    def select(self, cues: Sequence[Cue], index: int) -> None:
        if not 0<=index<len(cues):
            self.cue_id=None;self.position=-1
        else:
            self.cue_id=cues[index].cue_id;self.position=index

    def reconcile(self, cues: Sequence[Cue]) -> None:
        index=self.index(cues)
        if index>=0:self.position=index
        elif self.position>=0:self.select(cues,min(self.position,len(cues)-1))
