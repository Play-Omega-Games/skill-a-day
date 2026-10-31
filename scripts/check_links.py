"""Live-check every link in plans/curricula.json (or a custom plan): HTTP 200 after redirects,
on the same host, with a page title. Standard library only.

    python3 scripts/check_links.py [plan.json]
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = 'Mozilla/5.0 (compatible; OmegaSkillADay/1.0; +https://github.com/Play-Omega-Games/skill-a-day)'


def check_url(url, tries=2):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html'})
            with urllib.request.urlopen(req, timeout=25) as r:
                body = r.read(400000).decode('utf-8', 'ignore')
                final = r.geturl()
                title = re.search(r'<title[^>]*>(.*?)</title>', body, re.S | re.I)
                same = urllib.parse.urlparse(final).netloc == urllib.parse.urlparse(url).netloc
                return {'url': url, 'ok': r.status == 200 and same, 'status': r.status, 'final': final,
                        'title': (title.group(1).strip()[:90] if title else '')}
        except urllib.error.HTTPError as e:
            last = {'url': url, 'ok': False, 'status': e.code, 'final': url, 'title': ''}
        except Exception as e:  # noqa: BLE001
            last = {'url': url, 'ok': False, 'status': type(e).__name__, 'final': url, 'title': ''}
        time.sleep(2 * (i + 1))
    return last


def urls_in(obj):
    return sorted(set(re.findall(r'https://[^\s"\)]+', json.dumps(obj, ensure_ascii=False))))


if __name__ == '__main__':
    import urllib.parse  # noqa: F401
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'plans' / 'curricula.json'
    urls = urls_in(json.loads(path.read_text()))
    bad = 0
    for u in urls:
        r = check_url(u)
        bad += not r['ok']
        print(('OK  ' if r['ok'] else 'FAIL'), r['status'], u, '|', r['title'])
        time.sleep(0.5)
    print(f'{len(urls) - bad} of {len(urls)} links OK')
    sys.exit(1 if bad else 0)
