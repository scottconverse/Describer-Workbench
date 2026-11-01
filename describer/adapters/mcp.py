# SPDX-License-Identifier: Apache-2.0
"""MCP tools share the application service; stdio never writes protocol logs."""
from __future__ import annotations

import argparse
import os


def create_mcp(service):
    from mcp.server.fastmcp import FastMCP
    from mcp.server.transport_security import TransportSecuritySettings
    mcp = FastMCP('Describer Workbench', streamable_http_path='/', json_response=True,
                 transport_security=TransportSecuritySettings(
                     allowed_hosts=['127.0.0.1','127.0.0.1:*','localhost','localhost:*','[::1]','[::1]:*'],
                     allowed_origins=['http://127.0.0.1','http://127.0.0.1:*','http://localhost','http://localhost:*']))

    @mcp.tool()
    def capabilities() -> dict:
        """List supported operations, version and resource limits."""
        return service.capabilities()

    @mcp.tool()
    def list_models(settings: dict | None = None) -> list:
        """Discover Ollama models without downloading or generating."""
        return service.models(settings)

    @mcp.tool()
    def submit_description(source: str, settings: dict | None = None, prompt: str = '', start: float = 0,
                           duration: float | None = None) -> dict:
        """Start durable audio description. Returns a job ID. Poll until done, error or cancelled; never poll a terminal job forever."""
        return service.submit(source=source, settings=settings, prompt=prompt, start=start, duration=duration)

    @mcp.tool()
    def submit_batch(items: list[dict]) -> list:
        """Submit up to20 jobs; individual errors are returned in input order."""
        return service.submit_batch(items)

    @mcp.tool()
    def get_job(job_id: str) -> dict:
        """Get progress. done/error/cancelled/interrupted are terminal; errors require action, not more polling."""
        return service.get_job(job_id)

    @mcp.tool()
    def list_jobs(limit: int = 50, state: str | None = None) -> list:
        """List durable jobs, optionally by state."""
        return service.list_jobs(limit, state)

    @mcp.tool()
    def cancel_job(job_id: str) -> dict:
        """Cancel queued work or request cooperative cancellation of running work; checkpoints remain."""
        return service.cancel(job_id)

    @mcp.tool()
    def resume_job(job_id: str, settings: dict | None = None) -> dict:
        """Resume interrupted/failed/cancelled work. Changed source/model/settings invalidate checkpoints."""
        return service.resume(job_id, settings)

    @mcp.tool()
    def read_descriptions(job_id: str, offset: int = 0, limit: int = 100,
                          start: float | None = None, end: float | None = None) -> dict:
        """Read paged cues with event evidence, uncertainty and pause dispositions; only after done."""
        return service.read(job_id, offset, limit, start, end)

    @mcp.tool()
    def get_coverage(job_id: str) -> dict:
        """Read known event dispositions and unresolved details. This is not an accuracy/compliance certificate."""
        return service.coverage(job_id)

    @mcp.tool()
    def edit_descriptions(job_id: str, revision: int, cues: list[dict] | None = None,
                          glossary: str | None = None) -> dict:
        """Update cues/glossary with optimistic revision checking. Changed cues require re-planning."""
        return service.edit(job_id, revision, cues, glossary)

    @mcp.tool()
    def export_descriptions(job_id: str, export_format: str = 'mp4', settings: dict | None = None,
                            mode: str = 'complete') -> dict:
        """Start export job. Complete media includes pause narration by extending time. in-gap-only is explicitly incomplete."""
        return service.export_job(job_id, export_format, settings, mode)

    @mcp.tool()
    def ask_scene(source: str, question: str, start: float = 0, duration: float = 10,
                  settings: dict | None = None) -> dict:
        """Submit a scene-question job; read_scene returns the answer after done."""
        return service.submit(source=source, operation='ask', prompt=question, start=start, duration=duration, settings=settings)

    @mcp.tool()
    def explore_scene(source: str, start: float = 0, duration: float = 2,
                      settings: dict | None = None) -> dict:
        """Submit a spatial scene exploration job."""
        return service.submit(source=source, operation='explore', start=start, duration=duration, settings=settings)

    @mcp.tool()
    def read_scene(job_id: str) -> dict:
        """Read a completed scene answer or validated spatial layout."""
        return service.scene_result(job_id)

    @mcp.tool()
    def preview_voice(source: str, text: str, settings: dict | None = None) -> dict:
        """Generate a preview WAV as a durable job without changing saved descriptions."""
        return service.submit(source=source, operation='voice-preview', prompt=text, settings=settings)

    @mcp.tool()
    def get_artifact(job_id: str) -> dict:
        """Get artifact metadata/path after export or voice-preview completes; media is not embedded in tool responses."""
        job = service.get_job(job_id)
        if job['state'] != 'done':
            raise ValueError('Job is not done')
        return job.get('artifact', {})

    return mcp


def main(argv=None):
    parser = argparse.ArgumentParser(description='Describer MCP stdio client/server')
    parser.add_argument('--workspace')
    parser.add_argument('--server-url', help='Attach to an existing owning HTTP service')
    args = parser.parse_args(argv)
    if args.server_url:
        from .remote import RemoteService
        service = RemoteService(args.server_url, os.environ.get('DESCRIBER_API_TOKEN', ''))
    else:
        from ..engine import get_service
        service = get_service(args.workspace)
    try:
        create_mcp(service).run(transport='stdio')
    finally:
        service.close()


if __name__ == '__main__':
    main()
