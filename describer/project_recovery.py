"""Bounded local drafts, separate from explicit saves and engine job recovery."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
from uuid import uuid4

from .engine.core import atomic_json
from .project import Project


class DraftStore:
    max_files=20
    max_bytes=50*1024*1024
    max_snapshot_bytes=10*1024*1024
    per_project=3

    def __init__(self,root):
        self.root=Path(root).resolve()
        self.session=uuid4().hex
        self.last_digest=None

    def entries(self):
        rows=[]
        if not self.root.exists():return rows
        for path in self.root.glob('draft-*.adproject'):
            if path.is_symlink() or path.resolve().parent!=self.root:continue
            try:
                if path.stat().st_size>self.max_snapshot_bytes:continue
                data=json.loads(path.read_text(encoding='utf-8'))
                meta=data['_recovery']
                if not isinstance(meta.get('created_ns'),int) or not isinstance(meta.get('session'),str):continue
                rows.append((path,meta))
            except (OSError,ValueError,KeyError,TypeError):continue
        return sorted(rows,key=lambda row:row[1]['created_ns'],reverse=True)

    def snapshot(self,project,original=None,editor=None):
        if len({c.cue_id for c in project.cues})!=len(project.cues):raise ValueError('Duplicate description identity; recovery snapshot skipped.')
        content={'version':2,**asdict(project)}
        key=hashlib.sha256((str(original or '')+'\0'+project.video).encode()).hexdigest()
        digest=hashlib.sha256(json.dumps([content,editor],sort_keys=True).encode()).hexdigest()
        if digest==self.last_digest:return None
        content['_recovery']={'created_ns':time.time_ns(),'session':self.session,'key':key,'original':str(original or ''),'editor':editor}
        media=Path(project.video)
        if media.is_file():
            info=media.stat();content['_recovery']['media_stat']=[info.st_size,info.st_mtime_ns]
        if len(json.dumps(content,ensure_ascii=False,indent=2).encode('utf-8'))>self.max_snapshot_bytes:raise ValueError('Project exceeds the 10 MiB automatic recovery limit. Save it explicitly.')
        self.root.mkdir(parents=True,exist_ok=True)
        target=self.root/('draft-'+uuid4().hex+'.adproject')
        atomic_json(target,content)
        self.last_digest=digest
        count=0;size=0;projects={}
        for path,meta in self.entries():
            length=path.stat().st_size;ident=meta.get('key','')
            if count>=self.max_files or size+length>self.max_bytes or projects.get(ident,0)>=self.per_project:
                path.unlink()
            else:count+=1;size+=length;projects[ident]=projects.get(ident,0)+1
        return target

    def clear_session(self):
        for path,meta in self.entries():
            if meta['session']==self.session:path.unlink()
        self.last_digest=None

    def load(self,path):
        path=Path(path)
        if path.is_symlink() or path.resolve().parent!=self.root:raise ValueError('Not a local recovery snapshot.')
        meta=next((meta for candidate,meta in self.entries() if candidate==path),None)
        if meta is None:raise ValueError('Recovery snapshot is missing or invalid.')
        return Project.load(path),meta
