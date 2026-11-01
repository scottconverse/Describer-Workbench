# SPDX-License-Identifier: Apache-2.0
"""Scriptable CLI. Long local commands wait; remote submissions may return immediately."""
import argparse
import json
import os
import sys
import time
from pathlib import Path


def wait(service, job_id):
    while True:
        job = service.get_job(job_id)
        if job['state'] in ('done','error','cancelled','interrupted'):
            if job['state'] != 'done':raise RuntimeError(job.get('error') or job['state'])
            return job
        time.sleep(.1)


def main(argv=None):
    from . import __version__
    parser = argparse.ArgumentParser(prog='describer')
    parser.add_argument('--version',action='version',version=__version__)
    parser.add_argument('--workspace');parser.add_argument('--server-url');parser.add_argument('--settings')
    sub = parser.add_subparsers(dest='command',required=True)
    for name in ('describe','ask','explore','voice'):
        p=sub.add_parser(name);p.add_argument('source');p.add_argument('--prompt',default='')
        p.add_argument('--start',type=float,default=0);p.add_argument('--duration',type=float)
        p.add_argument('--no-wait',action='store_true')
    p=sub.add_parser('batch');p.add_argument('file')
    p=sub.add_parser('jobs');p.add_argument('--limit',type=int,default=50);p.add_argument('--state')
    for name in ('status','coverage','cancel','resume','read','export','edit','scene'):
        p=sub.add_parser(name);p.add_argument('job_id')
        if name=='read':
            p.add_argument('--offset',type=int,default=0);p.add_argument('--limit',type=int,default=100)
            p.add_argument('--start',type=float);p.add_argument('--end',type=float)
        if name=='export':
            p.add_argument('--format',default='mp4',choices=['mp4','mp3','wav','srt','vtt','txt','json'])
            p.add_argument('--mode',default='complete',choices=['complete','in-gap-only'])
        if name=='edit':p.add_argument('file',help='JSON with revision and optional cues/glossary')
    sub.add_parser('models');sub.add_parser('capabilities');sub.add_parser('mcp')
    p=sub.add_parser('assets');p.add_argument('action',choices=['provision']);p.add_argument('--destination')
    p=sub.add_parser('serve');p.add_argument('--port',type=int,default=8796);p.add_argument('--without-mcp',action='store_true')
    args=parser.parse_args(argv)
    service=None
    try:
        if args.command=='assets':
            from .engine.assets import provision
            print(json.dumps({'speech_model':str(provision(args.destination))}));return 0
        settings=json.loads(Path(args.settings).read_text('utf-8')) if args.settings else {}
        for key,env in [('gemini_key','DESCRIBER_GEMINI_API_KEY'),('openai_key','DESCRIBER_OPENAI_API_KEY'),('ollama_key','DESCRIBER_OLLAMA_API_KEY')]:
            if os.environ.get(env):settings[key]=os.environ[env]
        from .engine import DescriptionService
        if args.server_url:
            from .adapters.remote import RemoteService
            service=RemoteService(args.server_url,os.environ.get('DESCRIBER_API_TOKEN',''))
        else:service=DescriptionService(args.workspace,settings)
        command=args.command
        if command=='serve':
            if args.server_url:raise ValueError('serve must own a local workspace')
            import uvicorn
            from .adapters.http import create_app
            uvicorn.run(create_app(service,os.environ.get('DESCRIBER_API_TOKEN',''),not args.without_mcp),host='127.0.0.1',port=args.port)
            return 0
        if command=='mcp':
            from .adapters.mcp import create_mcp
            create_mcp(service).run(transport='stdio');return 0
        if command in ('describe','ask','explore','voice'):
            if args.no_wait and not args.server_url:raise ValueError('--no-wait requires --server-url')
            value=service.submit(source=args.source,settings=settings,prompt=args.prompt,start=args.start,duration=args.duration,operation={'voice':'voice-preview'}.get(command,command))
            if not args.no_wait:value=wait(service,value['id'])
        elif command=='batch':
            value=service.submit_batch(json.loads(Path(args.file).read_text('utf-8')))
            if not args.server_url:
                for item in value:
                    if 'job' in item:
                        try:item['job']=wait(service,item['job']['id'])
                        except RuntimeError as exc:item['error']=str(exc)
        elif command=='jobs':value=service.list_jobs(args.limit,args.state)
        elif command=='status':value=service.get_job(args.job_id)
        elif command=='read':value=service.read(args.job_id,args.offset,args.limit,args.start,args.end)
        elif command=='coverage':value=service.coverage(args.job_id)
        elif command=='scene':value=service.scene_result(args.job_id)
        elif command=='cancel':value=service.cancel(args.job_id)
        elif command=='resume':
            value=service.resume(args.job_id,settings)
            if not args.server_url:value=wait(service,args.job_id)
        elif command=='export':
            value=service.export_job(args.job_id,args.format,settings,args.mode)
            if not args.server_url:value=wait(service,value['id'])
        elif command=='edit':value=service.edit(args.job_id,**json.loads(Path(args.file).read_text('utf-8')))
        elif command=='models':value=service.models(settings)
        else:value=service.capabilities()
        print(json.dumps(value,ensure_ascii=False,indent=2));return 0
    except (ValueError,RuntimeError,OSError,KeyError) as exc:
        print(json.dumps({'error':str(exc)}),file=sys.stderr);return 1
    finally:
        if service is not None:service.close()


if __name__=='__main__':raise SystemExit(main())
