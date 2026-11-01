# SPDX-License-Identifier: Apache-2.0
"""Attach stdio/CLI clients to an existing HTTP engine; never open a second owner."""
import json
import urllib.error
import urllib.request
from urllib.parse import urlencode, urlsplit


class RemoteService:
    def __init__(self, url, token):
        parts = urlsplit(url)
        if parts.scheme not in ('http','https') or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError('Invalid engine URL')
        if parts.scheme == 'http' and parts.hostname not in ('127.0.0.1','localhost','::1'):
            raise ValueError('Remote engine requires HTTPS')
        self.url, self.token = url.rstrip('/'), token

    def request(self, method, path, body=None):
        headers = {'Authorization':'Bearer '+self.token, 'Content-Type':'application/json'}
        req = urllib.request.Request(self.url+path, method=method, headers=headers,
                                     data=json.dumps(body).encode() if body is not None else None)
        from ..models import NoRedirect
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=120) as response:
            return json.load(response)

    def capabilities(self):return self.request('GET','/capabilities')
    def models(self, settings=None):return self.request('POST','/models',settings or {})
    def submit(self, **kwargs):return self.request('POST','/jobs',kwargs)
    def submit_batch(self, items):return self.request('POST','/jobs/batch',items)
    def get_job(self, job_id):return self.request('GET',f'/jobs/{job_id}')
    def list_jobs(self, limit=50, state=None):return self.request('GET','/jobs?'+urlencode(dict(limit=limit,**({'state':state} if state else {}))))
    def cancel(self, job_id):return self.request('POST',f'/jobs/{job_id}/cancel')
    def resume(self, job_id, settings=None):return self.request('POST',f'/jobs/{job_id}/resume',settings or {})
    def read(self, job_id, offset=0, limit=100, start=None, end=None):
        params = {k:v for k,v in dict(offset=offset,limit=limit,start=start,end=end).items() if v is not None}
        return self.request('GET',f'/jobs/{job_id}/descriptions?'+urlencode(params))
    def coverage(self, job_id):return self.request('GET',f'/jobs/{job_id}/coverage')
    def edit(self, job_id, revision, cues=None, glossary=None):
        return self.request('PATCH',f'/jobs/{job_id}/project',dict(revision=revision,cues=cues,glossary=glossary))
    def export_job(self, job_id, export_format='mp4', settings=None, mode='complete'):
        return self.request('POST',f'/jobs/{job_id}/export',dict(export_format=export_format,settings=settings,mode=mode))
    def scene_result(self, job_id):return self.request('GET',f'/jobs/{job_id}/scene')
    def close(self):pass
