"""Render static documentation. Install docs/requirements.txt; no app runtime needed."""
import argparse
import html
import re
import shutil
import tomllib
from urllib.parse import urljoin, urlsplit
from pathlib import Path
import markdown

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://describer-workbench.sconverse.chatgpt.site'
REPO = 'https://github.com/scottconverse/Describer-Workbench'
VERSION = tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
DOC_STATUS = 'Development candidate '+VERSION

def downloadable_markdown(source):
    """Keep navigation usable after a guide is saved outside the source tree."""
    targets = {'USER-MANUAL.md': ORIGIN+'/manual.html',
               'ARCHITECTURE.md': ORIGIN+'/architecture.html',
               'DEVELOPER-GUIDE.md': ORIGIN+'/developer.html',
               'CODE-SIGNING.md': REPO+'/blob/main/docs/CODE-SIGNING.md',
               'AI-CONNECTIONS.md': REPO+'/blob/main/docs/AI-CONNECTIONS.md',
               'V052-ACCEPTANCE.md': REPO+'/blob/main/docs/V052-ACCEPTANCE.md',
               'V060-ACCEPTANCE.md': REPO+'/blob/main/docs/V060-ACCEPTANCE.md',
               'V051-ACCEPTANCE.md': REPO+'/blob/main/docs/V051-ACCEPTANCE.md',
               'V050-ACCEPTANCE.md': REPO+'/blob/main/docs/V050-ACCEPTANCE.md',
               '../THIRD-PARTY-NOTICES.md': REPO+'/blob/main/THIRD-PARTY-NOTICES.md'}
    def replace(match):
        target = match[2]
        if urlsplit(target).scheme or target.startswith('#'): return match[0]
        path, separator, fragment = target.partition('#')
        resolved = targets.get(path, urljoin(ORIGIN+'/', path))
        return match[1]+resolved+(separator+fragment if separator else '')+match[3]
    return re.sub(r'(!?\[[^\]]*\]\()([^\)]+)(\))', replace, source)

def render(source, title, filename):
    source = re.sub(r'```mermaid\n(.*?)```', lambda m: '<details class="diagram-source"><summary>Mermaid diagram source (text)</summary>\n\n```text\n'+m[1]+'```\n\n</details>', source, flags=re.S)
    md = markdown.Markdown(extensions=['tables','fenced_code','toc','md_in_html'], extension_configs={'toc':{'permalink':False}})
    body = md.convert(source)
    body=body.replace('href="AI-CONNECTIONS.md','href="'+REPO+'/blob/main/docs/AI-CONNECTIONS.md')
    body=body.replace('href="V060-ACCEPTANCE.md','href="'+REPO+'/blob/main/docs/V060-ACCEPTANCE.md')
    for old,new in [('USER-MANUAL.md','manual.html'),('ARCHITECTURE.md','architecture.html'),('DEVELOPER-GUIDE.md','developer.html'),('CODE-SIGNING.md',REPO+'/blob/main/docs/CODE-SIGNING.md'),('V052-ACCEPTANCE.md',REPO+'/blob/main/docs/V052-ACCEPTANCE.md'),('V051-ACCEPTANCE.md',REPO+'/blob/main/docs/V051-ACCEPTANCE.md'),('V050-ACCEPTANCE.md',REPO+'/blob/main/docs/V050-ACCEPTANCE.md'),('../THIRD-PARTY-NOTICES.md',REPO+'/blob/main/THIRD-PARTY-NOTICES.md')]:
        body=body.replace('href="'+old,'href="'+new)
    canonical = filename.removesuffix('.html')
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} — Describer Workbench</title><meta name="description" content="{html.escape(title)} for Describer Workbench {DOC_STATUS}, including everyday workflows, technical setup and verification limits."><link rel="stylesheet" href="docs.css"><link rel="icon" href="favicon.svg" type="image/svg+xml"><link rel="canonical" href="{ORIGIN}/{canonical}"></head><body><a class="skip" href="#content">Skip to content</a><header class="doc-header"><div class="wrap"><a class="brand" href="./"><img src="favicon.svg" width="36" height="36" alt=""><span>Describer <strong>Workbench</strong></span></a><nav aria-label="Documentation"><a href="manual.html">Manual</a><a href="architecture.html">Architecture</a><a href="developer.html">Developers</a><a href="{REPO}">GitHub ↗</a></nav></div></header><div class="doc-layout"><aside class="doc-sidebar" aria-label="Table of contents"><strong>IN THIS GUIDE</strong>{md.toc}</aside><main class="doc-content" id="content"><div class="doc-tools">{DOC_STATUS} · <a href="{filename.replace('.html','.md')}" download>Download Markdown</a> · Use your browser's Print command to save as PDF</div>{body}<div class="doc-bottom"><a href="./">← Back to Describer Workbench</a> · <a href="{REPO}/issues">Report an issue</a></div></main></div></body></html>'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(); out=args.output.resolve()
    # Never replace source or use a recursive delete during generation.
    if out==ROOT or out in (ROOT/'docs',ROOT/'website',ROOT/'describer') or ROOT.is_relative_to(out):
        parser.error('Choose a dedicated generated site output directory, separate from source.')
    out.mkdir(parents=True,exist_ok=True)
    for p in (ROOT/'website').iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    shutil.copytree(ROOT/'docs/diagrams',out/'diagrams',dirs_exist_ok=True)
    for src,title,name in [('USER-MANUAL.md','User manual','manual.html'),('ARCHITECTURE.md','Architecture guide','architecture.html'),('DEVELOPER-GUIDE.md','Developer guide','developer.html')]:
        source=(ROOT/'docs'/src).read_text(encoding='utf-8')
        (out/name).write_text(render(source,title,name),encoding='utf-8')
        (out/name.replace('.html','.md')).write_text(downloadable_markdown(source),encoding='utf-8')
    (out/'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {ORIGIN}/sitemap.xml\n',encoding='utf-8')
    (out/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>{ORIGIN}/{p}</loc></url>' for p in ['','manual','architecture','developer'])+'</urlset>',encoding='utf-8')
    print(f'Static site rendered to {out}')

if __name__=='__main__':main()
