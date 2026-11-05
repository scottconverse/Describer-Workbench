"""Documentation-only regressions; install docs/requirements.txt to run them."""
import importlib.util
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

HAS_MARKDOWN = importlib.util.find_spec('markdown') is not None

class Navigation(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.targets=[]; self.ids=set(); self.feed(text)
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.add(attrs['id'])
        for key in ('href','src'):
            if key in attrs:self.targets.append(attrs[key])

@unittest.skipUnless(HAS_MARKDOWN, 'Install docs/requirements.txt for documentation checks')
class DocumentationTests(unittest.TestCase):
    def test_generated_downloads_keep_navigation_outside_repo(self):
        import markdown
        from tools import build_site
        with tempfile.TemporaryDirectory() as tmp:
            with patch('sys.argv', ['build_site.py','--output',tmp]):build_site.main()
            for name in ('quick-start.md','manual.md','architecture.md','developer.md','unix.md','connections.md','signing.md'):
                text=(Path(tmp)/name).read_text(encoding='utf-8')
                links=Navigation(markdown.markdown(text,extensions=['fenced_code','tables'])).targets
                self.assertTrue(links)
                for target in links:
                    self.assertTrue(urlsplit(target).scheme=='https' or target.startswith('#'),(name,target))
                if name in ('manual.md','architecture.md','developer.md'):
                    self.assertIn(build_site.ORIGIN+'/diagrams/system.svg',links)
            self.assertIn(build_site.ORIGIN+'/architecture.html',Navigation(markdown.markdown((Path(tmp)/'manual.md').read_text(encoding='utf-8'))).targets)

    def test_generated_html_links_and_fragments_exist(self):
        from tools import build_site
        with tempfile.TemporaryDirectory() as tmp:
            with patch('sys.argv', ['build_site.py','--output',tmp]):build_site.main()
            pages={p.name:Navigation(p.read_text(encoding='utf-8')) for p in Path(tmp).glob('*.html')}
            for name in ('manual','architecture','developer'):
                self.assertIn(f'rel="canonical" href="{build_site.ORIGIN}/{name}"', (Path(tmp)/(name+'.html')).read_text(encoding='utf-8'))
            sitemap=(Path(tmp)/'sitemap.xml').read_text(encoding='utf-8')
            self.assertNotIn('.html',sitemap)
            self.assertIn(build_site.ORIGIN+'/manual',sitemap)
            for name, page in pages.items():
                for target in page.targets:
                    url=urlsplit(target)
                    if url.scheme or url.netloc:continue
                    p=Path(tmp)/(url.path or name)
                    if p.is_dir():p=p/'index.html'
                    self.assertTrue(p.is_file(),(name,target))
                    if url.fragment and p.suffix=='.html':self.assertIn(url.fragment,pages[p.name].ids,(name,target))

    def test_primary_downloads_and_platform_instructions_are_visible(self):
        """A matching generated page can still advertise the wrong platforms."""
        from tools import build_site
        source=(build_site.ROOT/'website/index.html').read_text(encoding='utf-8')
        hero=source.split('<section class="hero"',1)[1].split('</section>',1)[0]
        for platform in ('windows','macos-arm64','macos-x64','linux'):
            self.assertIn(f'data-platform="{platform}"',hero)
        for extension in ('windows-x64.zip','macos-arm64.dmg','macos-x64.dmg','linux-x64.deb'):
            self.assertIn(extension,hero)
        self.assertNotIn('A Windows workspace',source)
        self.assertNotIn('<h3>Windows speech</h3>',source)
        for name in ('README.md','docs/QUICK-START.md','docs/USER-MANUAL.md'):
            text=(build_site.ROOT/name).read_text(encoding='utf-8')
            for target in ('macos-arm64.dmg','macos-x64.dmg','linux-x64.deb','windows-x64.zip'):
                self.assertIn(target,text,(name,target))
        architecture=(build_site.ROOT/'docs/ARCHITECTURE.md').read_text(encoding='utf-8')
        for concept in ('Keychain','Secret Service','ad-hoc','platforms.svg','manual replacement'):
            self.assertIn(concept,architecture)
        import xml.etree.ElementTree as ET
        for path in (build_site.ROOT/'docs/diagrams').glob('*.svg'):
            diagram=ET.fromstring(path.read_text(encoding='utf-8'))
            self.assertEqual(diagram.attrib['role'],'img')
            self.assertTrue(diagram.find('{http://www.w3.org/2000/svg}desc').text)

if __name__=='__main__':unittest.main()
