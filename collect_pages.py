"""Bounded, domain-allowlisted static HTML collector. Does not capture dynamic layout."""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
USER_AGENT = 'WebExtractLearning/1.0'
MAX_BYTES = 5_000_000


def canonical(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or '/', p.query, ''))


def collect(config, root=ROOT, limit_override=None, dry_run=False):
    domains = set(config.get('allowed_domains', []))
    seeds = config.get('seeds', [])
    if not domains or not seeds:
        raise ValueError('Fill seeds and allowed_domains in config/collection.json first.')
    pattern = re.compile(config.get('article_url_pattern', '.*'))
    discovery_pattern = re.compile(config.get('discovery_url_pattern', '.*'))
    limit = int(limit_override if limit_override is not None else config.get('max_pages', 10))
    max_fetch = int(config.get('max_fetches', 30))
    depth_limit = int(config.get('max_depth', 1))
    delay = max(0.1, float(config.get('delay_seconds', 1)))
    if not 1 <= limit <= 200 or not 1 <= max_fetch <= 1000 or not 0 <= depth_limit <= 3:
        raise ValueError('max_pages 1..200, max_fetches 1..1000, max_depth 0..3')

    def allowed(url):
        p = urlsplit(url)
        return p.scheme in ('http', 'https') and p.hostname in domains and not p.username

    if any(not allowed(s) for s in seeds):
        raise ValueError('Every seed must be http(s) and its exact hostname in allowed_domains.')
    if dry_run:
        return dict(dry_run=True, seeds=seeds, allowed_domains=sorted(domains), max_pages=limit, max_fetches=max_fetch)

    class RestrictedRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not allowed(newurl):
                raise ValueError('Redirect outside allowed domains: '+newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    opener = build_opener(RestrictedRedirect())
    robots, last = {}, {}

    def request(url):
        host = urlsplit(url).netloc
        time.sleep(max(0, delay - (time.monotonic()-last.get(host, 0))))
        try:
            with opener.open(Request(url, headers={'User-Agent': USER_AGENT}), timeout=20) as response:
                raw = response.read(MAX_BYTES+1)
                if len(raw) > MAX_BYTES:
                    raise ValueError('Response exceeds 5MB')
                return raw, response.geturl(), response.headers.get_content_type()
        finally:
            last[host] = time.monotonic()

    def permitted(url):
        p = urlsplit(url)
        origin = f'{p.scheme}://{p.netloc}'
        if origin not in robots:
            parser = RobotFileParser()
            try:
                raw, _, _ = request(origin+'/robots.txt')
                parser.parse(raw.decode('utf-8', errors='replace').splitlines())
            except Exception as exc:
                # A missing robots file permits access; connectivity/auth failures skip this host.
                if getattr(exc, 'code', None) == 404:
                    parser.parse([])
                else:
                    parser.disallow_all = True
            robots[origin] = parser
        return robots[origin].can_fetch(USER_AGENT, url)

    manifest_path = root/'reports/collection_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else []
    hashes = {x['content_hash'] for x in manifest if x.get('content_hash')}
    seen = set()  # Revisit seed/index pages on a later run to discover new articles.
    queue = deque((canonical(s), 0) for s in seeds)
    added, errors, skipped, attempts = [], [], [], 0
    while queue and len(added) < limit and attempts < max_fetch:
        url, depth = queue.popleft()
        if url in seen or not allowed(url):
            continue
        seen.add(url)
        attempts += 1
        try:
            if not permitted(url):
                raise ValueError('robots policy or robots fetch failure: skipped')
            raw, final, content_type = request(url)
            if not permitted(final):
                raise ValueError('redirect destination robots disallows access')
            if content_type not in ('text/html', 'application/xhtml+xml', 'application/xml', 'text/xml', 'application/rss+xml', 'application/atom+xml'):
                skipped.append(dict(url=url, reason='unsupported_content_type', content_type=content_type))
                continue
            soup = BeautifulSoup(raw, 'xml' if 'xml' in content_type else 'html.parser')
            if depth < depth_limit:
                links = [a.get('href') for a in soup.find_all(['a', 'link']) if a.get('href')]
                links += [n.get_text(strip=True) for n in soup.find_all(['loc', 'link']) if n.get_text(strip=True).startswith(('http://','https://'))]
                for link in links:
                    target = canonical(urljoin(final, link))
                    if allowed(target) and discovery_pattern.search(target) and target not in seen and len(queue)<2000:
                        queue.append((target, depth+1))
            if 'html' not in content_type or not pattern.search(final):
                skipped.append(dict(url=final, reason='discovery_only_or_url_filter'))
                continue
            for node in soup(['script', 'style']):
                node.decompose()
            text = ' '.join(soup.stripped_strings)
            if len(text) < int(config.get('min_text_chars', 200)):
                skipped.append(dict(url=final, reason='insufficient_static_text', text_chars=len(text), suggestion='Inspect in browser; save a rendered snapshot if article text is present.'))
                continue
            digest = hashlib.sha256(text.encode()).hexdigest()
            if digest in hashes:
                skipped.append(dict(url=final, reason='duplicate_content'))
                continue
            name = 'collected_'+hashlib.sha256(final.encode()).hexdigest()[:16]+'.html'
            # Reparse original so scripts/styles are preserved; base repairs relative resources.
            document = BeautifulSoup(raw, 'html.parser')
            if not document.head:
                head = document.new_tag('head');document.insert(0, head)
            for base in document.find_all('base'):
                base.decompose()
            document.head.insert(0, document.new_tag('base', href=final))
            path = root/'samples'/name
            path.parent.mkdir(exist_ok=True)
            path.write_text(str(document), encoding='utf-8')
            item = dict(file=name, url=final, seed_url=url, domain=urlsplit(final).hostname,
                        content_hash=digest, snapshot=hashlib.sha256(path.read_bytes()).hexdigest(),
                        fetched_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()), mode='static', text_chars=len(text))
            manifest[:] = [entry for entry in manifest if entry.get('file') != name]
            manifest.append(item);added.append(item);hashes.add(digest)
        except Exception as exc:
            errors.append(dict(url=url, error=str(exc)))
    manifest_path.parent.mkdir(exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    summary = dict(added=added, attempts=attempts, skipped=skipped, errors=errors)
    (root/'reports/collection_last_run.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT/'config/collection.json')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(collect(json.loads(args.config.read_text(encoding='utf-8-sig')), limit_override=args.limit, dry_run=args.dry_run),ensure_ascii=False,indent=2))
    except ValueError as exc:
        parser.error(str(exc))
