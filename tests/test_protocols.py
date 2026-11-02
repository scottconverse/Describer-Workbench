"""Actual HTTP/MCP framing and stdio initialization, no paid inference."""
import asyncio
import json
import os
import subprocess
import sys
from unittest.mock import patch

from describer.project import Project, Cue
from describer import __version__

from fastapi.testclient import TestClient

from describer.adapters.http import create_app
from describer.engine import DescriptionService


def test_http_auth_openapi_and_mcp_transport(tmp_path):
    service=DescriptionService(tmp_path/'engine')
    token='fixture-secret-1234567890'
    headers={'Authorization':'Bearer '+token}
    try:
        with TestClient(create_app(service,token),base_url='http://127.0.0.1') as client:
            assert client.get('/capabilities').status_code==401
            assert client.get('/capabilities',headers=dict(headers,Origin='https://outside.example')).status_code==403
            assert client.get('/capabilities',headers=headers).json()['version']==__version__
            schema=client.get('/openapi.json',headers=headers).json()
            assert '/jobs/{job_id}/export' in schema['paths']
            assert client.post('/jobs',headers=headers,json={'source':'does-not-exist'}).status_code==422
            assert client.patch('/jobs/'+'0'*32+'/project',headers=headers,json={'typo':True}).status_code==422
            assert client.post('/jobs/'+'0'*32+'/export',headers=headers,json={'typo':True}).status_code==422
            mh=dict(headers,Accept='application/json, text/event-stream')
            response=client.post('/mcp/',headers=mh,json={'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'acceptance','version':'1'}}})
            assert response.status_code==200,response.text
            assert response.json()['result']['serverInfo']['name']=='Describer Workbench'
            if response.headers.get('mcp-session-id'):mh['Mcp-Session-Id']=response.headers['mcp-session-id']
            mh['MCP-Protocol-Version']='2025-06-18'
            client.post('/mcp/',headers=mh,json={'jsonrpc':'2.0','method':'notifications/initialized'})
            response=client.post('/mcp/',headers=mh,json={'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'capabilities','arguments':{}}})
            assert response.status_code==200,response.text
            assert __version__ in response.text
            source=tmp_path/'source.mp4';source.write_bytes(b'fixture source')
            project=Project(str(source),3,[Cue(0,1,'A door opens.')])
            # Protocol fixture replaces inference only; real queue, storage, paging,
            # revision checks, script export and artifact delivery remain active.
            with patch('describer.engine.core.describe',return_value=project):
                job=client.post('/jobs',headers=headers,json={'project':{'video':str(source),'duration':3},'settings':{'allow_cloud':True}})
                assert job.status_code==202,job.text
                job_id=job.json()['id'];service.wait(job_id)
            response=client.post('/mcp/',headers=mh,json={'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'read_descriptions','arguments':{'job_id':job_id,'limit':1}}})
            assert response.status_code==200 and 'A door opens.' in response.text
            revision=service.get_job(job_id)['revision']
            assert client.patch(f'/jobs/{job_id}/project',headers=headers,json={'revision':revision,'glossary':'Same engine'}).status_code==200
            assert client.patch(f'/jobs/{job_id}/project',headers=headers,json={'revision':revision,'glossary':'Stale'}).status_code==422
            exported=client.post(f'/jobs/{job_id}/export',headers=headers,json={'export_format':'srt'})
            assert exported.status_code==202,exported.text
            export_id=exported.json()['id'];service.wait(export_id)
            assert 'A door opens.' in client.get(f'/jobs/{export_id}/artifact',headers=headers).text
            with patch('describer.services.synthesize',side_effect=AssertionError('Text export cannot synthesize')):
                script=client.post(f'/jobs/{job_id}/export',headers=headers,json={'export_format':'srt','settings':{'voice_engine':'OpenAI','allow_cloud':False}})
                assert script.status_code==202,script.text
                service.wait(script.json()['id'])
                response=client.post('/mcp/',headers=mh,json={'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'export_descriptions','arguments':{'job_id':job_id,'export_format':'srt','settings':{'voice_engine':'OpenAI','allow_cloud':False}}}})
                assert response.status_code==200,response.text
                assert not response.json()['result'].get('isError'),response.text

    finally:service.close()


def test_real_stdio_harness_and_cli(tmp_path):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    async def check():
        params=StdioServerParameters(command=sys.executable,args=['-m','describer.adapters.mcp','--workspace',str(tmp_path/'mcp')],env=dict(os.environ))
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                tools=await session.list_tools()
                assert {'submit_description','cancel_job','resume_job','edit_descriptions','export_descriptions','ask_scene','get_coverage'} <= {t.name for t in tools.tools}
                result=await session.call_tool('capabilities',{})
                assert not result.isError
                assert __version__ in str(result)
    asyncio.run(asyncio.wait_for(check(),30))
    completed=subprocess.run([sys.executable,'-m','describer.cli','--workspace',str(tmp_path/'cli'),'capabilities'],capture_output=True,text=True,timeout=20)
    assert completed.returncode==0,completed.stderr
    assert json.loads(completed.stdout)['version']==__version__
