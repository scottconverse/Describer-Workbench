"""Exercise a built portable CLI, HTTP server and real MCP stdio client."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
import urllib.request


def main():
    p=argparse.ArgumentParser();p.add_argument('--cli',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    args=p.parse_args();exe=args.cli.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    version=subprocess.run([str(exe),'--version'],capture_output=True,text=True,timeout=20)
    assert version.returncode==0 and version.stdout.strip()=='0.5.1',(version.stdout,version.stderr)
    caps=subprocess.run([str(exe),'--workspace',str(out/'cli'),'capabilities'],capture_output=True,text=True,timeout=20)
    assert caps.returncode==0,caps.stderr
    assert json.loads(caps.stdout)['max_concurrent_jobs']==1
    token=secrets.token_urlsafe(32);env=dict(os.environ,DESCRIBER_API_TOKEN=token)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    with (out/'http.log').open('wb') as log:
        proc=subprocess.Popen([str(exe),'--workspace',str(out/'http'),'serve','--port',str(port)],env=env,stdout=log,stderr=log,creationflags=0x08000000)
        try:
            started=time.monotonic()
            while True:
                assert proc.poll() is None,'Packaged HTTP server exited'
                try:
                    req=urllib.request.Request(f'http://127.0.0.1:{port}/capabilities',headers={'Authorization':'Bearer '+token})
                    with urllib.request.urlopen(req,timeout=2) as response:data=json.load(response)
                    assert data['version']=='0.5.1' and not data['telemetry'];break
                except OSError:
                    if time.monotonic()-started>30:raise
                    time.sleep(.1)
            req=urllib.request.Request(f'http://127.0.0.1:{port}/openapi.json',headers={'Authorization':'Bearer '+token})
            with urllib.request.urlopen(req,timeout=5) as response:schema=json.load(response)
            assert '/jobs/{job_id}/export' in schema['paths']
        finally:
            proc.terminate()
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
    async def check_mcp():
        from mcp import ClientSession,StdioServerParameters
        from mcp.client.stdio import stdio_client
        params=StdioServerParameters(command=str(exe),args=['--workspace',str(out/'mcp'),'mcp'],env=dict(os.environ))
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as client:
                await client.initialize();tools=await client.list_tools()
                assert len(tools.tools)==17
                value=await client.call_tool('capabilities',{})
                assert not value.isError and '0.5.1' in str(value)
                return len(tools.tools)
    count=asyncio.run(asyncio.wait_for(check_mcp(),40))
    result={'version':'0.5.1','portable_cli':True,'portable_http_openapi':True,'portable_mcp_stdio':True,'tools':count,'owned_http_stopped':proc.poll() is not None}
    (out/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))

if __name__=='__main__':main()
