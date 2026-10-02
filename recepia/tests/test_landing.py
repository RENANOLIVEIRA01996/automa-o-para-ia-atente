"""Public landing assets and route preservation, without external services."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

import pytest

from config import Settings, settings
from services.ai.public_links import recepia_signup_url, recepia_site_url

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
    for url, filename in [('/', 'landing/index.html'), ('/cadastro', 'landing/cadastro.html')]:
        response = client.get(url)
        assert response.status_code == 200
        assert '__PUBLIC_SITE_URL__' not in response.text
        assert '<link rel="canonical" href="' + settings.PUBLIC_SITE_URL + url + '">' in response.text
    for url, filename in [('/dashboard/', 'dashboard/index.html'),
                          ('/dashboard/saas.html', 'dashboard/saas.html'),
                          ('/dashboard/admin.html', 'dashboard/admin.html')]:
        response = client.get(url)
        assert response.status_code == 200
        assert response.content == (ROOT / filename).read_bytes()
    for url in ('/automacao-whatsapp-empresas', '/atendimento-whatsapp-inteligencia-artificial',
                '/agendamento-automatico-whatsapp', '/termos', '/privacidade'):
        assert client.get(url).status_code == 200
    assert client.get('/health').json() == {'status': 'ok'}


def test_assets_media_head_and_traversal(client):
    for name in ['landing.css', 'landing.js', 'services.css', 'favicon.svg', 'secretaria-fallback.webp',
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
            assert href == '/cadastro'


def test_seo_documents(client):
    import re
    html = client.get('/').text
    data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html).group(1))
    assert data['@type'] == 'SoftwareApplication'
    assert 'aggregateRating' not in data
    root = ET.fromstring(client.get('/sitemap.xml').content)
    urls = [node.text for node in root.iter() if node.tag.endswith('loc')]
    expected_paths = ('/', '/automacao-whatsapp-empresas',
                      '/atendimento-whatsapp-inteligencia-artificial',
                      '/agendamento-automatico-whatsapp', '/termos', '/privacidade')
    assert set(urls) == {settings.PUBLIC_SITE_URL + path for path in expected_paths}
    assert data['url'] in urls
    assert 'Disallow: /dashboard' not in client.get('/robots.txt').text
    assert f'Sitemap: {settings.PUBLIC_SITE_URL}/sitemap.xml' in client.get('/robots.txt').text
    for path in expected_paths[:4]:
        page = client.get(path)
        parser = LandingParser()
        parser.feed(page.text)
        assert len(parser.headings) == 1
        assert f'<meta property="og:url" content="{settings.PUBLIC_SITE_URL}{path}">' in page.text
        assert f'<meta property="og:image" content="{settings.PUBLIC_SITE_URL}/assets/secretaria-fallback.webp">' in page.text
        assert 'X-Robots-Tag' not in page.headers
    for path in ('/cadastro', '/entrar', '/dashboard/', '/dashboard/saas.html',
                 '/dashboard/admin.html', '/openapi.json'):
        assert 'noindex' in client.get(path).headers['X-Robots-Tag']


def test_public_domain_changes_in_one_setting(client, monkeypatch):
    monkeypatch.setattr(settings, 'PUBLIC_SITE_URL', 'https://site.example')
    assert '<link rel="canonical" href="https://site.example/">' in client.get('/').text
    assert '<meta property="og:image" content="https://site.example/assets/secretaria-fallback.webp">' in client.get('/').text
    assert 'https://site.example/sitemap.xml' in client.get('/robots.txt').text
    assert 'https://site.example/automacao-whatsapp-empresas' in client.get('/sitemap.xml').text
    assert 'data-domain="site.example"' in client.get('/cadastro').text
    assert recepia_site_url() == 'https://site.example/'
    assert recepia_signup_url() == 'https://site.example/cadastro'


def test_public_domain_rejects_unsafe_origins():
    for value in ('http://example.com', 'https://example.com/path',
                  'https://user:pass@example.com', 'https://example.com\n<script>'):
        with pytest.raises(ValueError):
            Settings.validar_site_publico(value)


def test_service_pages_have_distinct_relevant_content(client):
    topics = {
        '/automacao-whatsapp-empresas': 'Automação de WhatsApp para empresas',
        '/atendimento-whatsapp-inteligencia-artificial': 'Atendimento pelo WhatsApp com inteligência artificial',
        '/agendamento-automatico-whatsapp': 'Agendamento automático pelo WhatsApp',
    }
    for path, topic in topics.items():
        html = client.get(path).text
        assert topic.casefold() in html.casefold()
        assert f'<title>{topic} | Recepia</title>' in html
        assert 'name="description"' in html
        assert '<h1>' in html
        assert '/cadastro' in html
        assert '__PUBLIC_SITE_URL__' not in html
