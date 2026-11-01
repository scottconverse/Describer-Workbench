# SPDX-License-Identifier: Apache-2.0
"""Loopback REST/OpenAPI and MCP share one owner, queue and job IDs."""
import hmac
from contextlib import asynccontextmanager
from pathlib import Path


def create_app(service, token, enable_mcp=True):
    if not token or len(token) < 16:
        raise ValueError('Set DESCRIBER_API_TOKEN to a secret of at least16 characters')
    from fastapi import FastAPI, Request
    from fastapi.responses import FileResponse, JSONResponse
    from pydantic import BaseModel, ConfigDict, Field
    from starlette.middleware.trustedhost import TrustedHostMiddleware

    class Submission(BaseModel):
        model_config = ConfigDict(extra='forbid')
        source: str | None = None
        project: dict | None = None
        settings: dict = Field(default_factory=dict)
        prompt: str = ''
        start: float = Field(default=0, ge=0)
        duration: float | None = Field(default=None, gt=0)
        operation: str = 'describe'
        export_format: str | None = None
        mode: str = 'complete'

    class Edit(BaseModel):
        model_config = ConfigDict(extra='forbid')
        revision: int = Field(ge=0)
        cues: list[dict] | None = None
        glossary: str | None = None

    class Export(BaseModel):
        model_config = ConfigDict(extra='forbid')
        export_format: str = 'mp4'
        settings: dict | None = None
        mode: str = 'complete'

    from .mcp import create_mcp
    mcp = create_mcp(service) if enable_mcp else None

    @asynccontextmanager
    async def lifespan(app):
        if mcp:
            async with mcp.session_manager.run():
                yield
        else:
            yield

    app = FastAPI(title='Describer Workbench', version='0.5.0', lifespan=lifespan,
                  telemetry={'tracing':False,'metrics':False,'logs':False,'operation_spans':False,'auto_configure':False})
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost','127.0.0.1','[::1]'])

    @app.middleware('http')
    async def boundary(request: Request, call_next):
        supplied = request.headers.get('authorization', '')
        if not hmac.compare_digest(supplied, 'Bearer '+token):
            return JSONResponse({'detail':'Bearer token required'}, status_code=401)
        if request.headers.get('origin') and request.headers['origin'].rstrip('/') != str(request.base_url).rstrip('/'):
            return JSONResponse({'detail':'Cross-origin access refused'}, status_code=403)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({'detail':str(exc)}, status_code=422)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({'detail':'Job not found'}, status_code=404)

    @app.get('/capabilities')
    def capabilities():return service.capabilities()

    @app.post('/models')
    def models(settings: dict):return service.models(settings)

    @app.post('/jobs', status_code=202)
    def submit(body: Submission):return service.submit(**body.model_dump())

    @app.post('/jobs/batch', status_code=202)
    def batch(items: list[Submission]):return service.submit_batch([item.model_dump() for item in items])

    @app.get('/jobs')
    def jobs(limit: int = 50, state: str | None = None):return service.list_jobs(limit, state)

    @app.get('/jobs/{job_id}')
    def job(job_id: str):return service.get_job(job_id)

    @app.post('/jobs/{job_id}/cancel')
    def cancel(job_id: str):return service.cancel(job_id)

    @app.post('/jobs/{job_id}/resume', status_code=202)
    def resume(job_id: str, settings: dict | None = None):return service.resume(job_id, settings)

    @app.get('/jobs/{job_id}/descriptions')
    def read(job_id: str, offset: int = 0, limit: int = 100, start: float | None = None, end: float | None = None):
        return service.read(job_id, offset, limit, start, end)

    @app.get('/jobs/{job_id}/coverage')
    def coverage(job_id: str):return service.coverage(job_id)

    @app.patch('/jobs/{job_id}/project')
    def edit(job_id: str, body: Edit):return service.edit(job_id, **body.model_dump())

    @app.post('/jobs/{job_id}/export', status_code=202)
    def export(job_id: str, body: Export):return service.export_job(job_id, **body.model_dump())

    @app.get('/jobs/{job_id}/scene')
    def scene(job_id: str):return service.scene_result(job_id)

    @app.get('/jobs/{job_id}/artifact')
    def artifact(job_id: str):
        data = service.get_job(job_id)
        if data['state'] != 'done' or 'artifact' not in data:
            raise ValueError('No completed artifact')
        path = Path(data['artifact']['path']).resolve()
        if not path.is_relative_to(service.root.resolve()):
            raise ValueError('Artifact is outside this workspace')
        return FileResponse(path, filename=path.name)

    if mcp:
        app.mount('/mcp', mcp.streamable_http_app())
    return app
