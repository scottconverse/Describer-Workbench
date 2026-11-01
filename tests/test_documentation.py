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
            for name in ('manual.md','architecture.md'):
                text=(Path(tmp)/name).read_text(encoding='utf-8')
                links=Navigation(markdown.markdown(text,extensions=['fenced_code','tables'])).targets
                self.assertTrue(links)
                for target in links:
                    self.assertTrue(urlsplit(target).scheme=='https' or target.startswith('#'),(name,target))
                self.assertIn(build_site.ORIGIN+'/diagrams/system.svg',links)
            self.assertIn(build_site.ORIGIN+'/architecture.html',Navigation(markdown.markdown((Path(tmp)/'manual.md').read_text(encoding='utf-8'))).targets)

    def test_generated_html_links_and_fragments_exist(self):
        from tools import build_site
        with tempfile.TemporaryDirectory() as tmp:
            with patch('sys.argv', ['build_site.py','--output',tmp]):build_site.main()
            pages={p.name:Navigation(p.read_text(encoding='utf-8')) for p in Path(tmp).glob('*.html')}
            for name in ('manual','architecture'):
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

if __name__=='__main__':unittest.main()
