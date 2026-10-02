"""Public landing assets and route preservation, without external services."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]


class LandingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.anchors = []
        self.headings = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            assert attrs['id'] not in self.ids, 'Duplicate HTML id'
            self.ids.add(attrs['id'])
        if tag == 'a':
            self.anchors.append(attrs)
        if tag == 'h1':
            self.headings.append(tag)


def test_landing_and_existing_public_routes(client):
    for url, filename in [('/', 'landing/index.html'), ('/cadastro', 'landing/cadastro.html'),
                          ('/dashboard/saas.html', 'dashboard/saas.html'),
                          ('/dashboard/admin.html', 'dashboard/admin.html')]:
        response = client.get(url)
        assert response.status_code == 200
        assert response.content == (ROOT / filename).read_bytes()
    assert client.get('/health').json() == {'status': 'ok'}


def test_assets_media_head_and_traversal(client):
    for name in ['landing.css', 'landing.js', 'favicon.svg', 'secretaria-fallback.webp',
                 'secretaria-mobile.webp', 'recepia-secretaria-loop.mp4', 'recepia-secretaria-loop.webm']:
        response = client.get('/assets/' + name)
        assert response.status_code == 200
        assert response.content == (ROOT / 'landing/assets' / name).read_bytes()
    assert client.head('/assets/recepia-secretaria-loop.mp4').headers['content-type'] == 'video/mp4'
    for url in ['/assets/%2e%2e/config.py', '/assets/%2e%2e/%2e%2e/config.py', '/assets/missing.mp4']:
        assert client.get(url).status_code == 404


def test_landing_anchors_and_signup_destination():
    parser = LandingParser()
    parser.feed((ROOT / 'landing/index.html').read_text())
    assert len(parser.headings) == 1
    for anchor in parser.anchors:
        href = anchor.get('href', '')
        if href.startswith('#'):
            assert href[1:] in parser.ids
        if 'signup' in anchor.get('class', '').split():
            assert href == 'https://recepia.132-226-243-173.sslip.io/cadastro'


def test_seo_documents(client):
    import re
    html = client.get('/').text
    data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html).group(1))
    assert data['@type'] == 'SoftwareApplication'
    assert 'aggregateRating' not in data
    root = ET.fromstring(client.get('/sitemap.xml').content)
    urls = [node.text for node in root.iter() if node.tag.endswith('loc')]
    assert data['url'] in urls
    assert not any('/cadastro' in url for url in urls)
    assert 'Disallow: /dashboard/' in client.get('/robots.txt').text
