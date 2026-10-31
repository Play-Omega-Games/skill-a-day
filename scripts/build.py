"""Build plans/curricula.json from scripts/curricula.py. Standard library only.

    python3 scripts/build.py              # curricula only
    python3 scripts/build.py --words DIR  # also rebuild data/typing_words.txt from DIR (maintainers only)
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import curricula as C  # noqa: E402

LEVELS = {1: 'Foundations', 2: 'Foundations', 3: 'Foundations', 4: 'Building', 5: 'Building', 6: 'Building'}


def build_curricula():
    skills = []
    by_id = {s['id']: s for s in C.SKILLS}
    for sid in C.MENU_ORDER:
        s = dict(by_id[sid])
        stages = []
        for n, st in enumerate(s['stages'], 1):
            st = dict(st)
            st['stage'] = n
            st['level'] = LEVELS[n]
            st['drills'] = [dict(d, drill=k) for k, d in enumerate(st['drills'], 1)]
            st.setdefault('gen', {})
            stages.append(st)
        s['stages'] = stages
        s['source'] = 'omega'
        skills.append(s)
    out = {
        'meta': {
            'name': 'Skill a Day: curricula',
            'version': 1,
            'session_minutes': {'warmup': 3, 'practice': 10, 'wrapup': 2},
            'stages_per_skill': 6,
            'drills_per_stage': 6,
            'levels': {'Foundations': [1, 2, 3], 'Building': [4, 5, 6]},
            'license': 'CC0 1.0',
        },
        'menu': C.MENU_ORDER,
        'skills': skills,
        'speaking_topics': C.SPEAKING_TOPICS,
    }
    (ROOT / 'plans').mkdir(exist_ok=True)
    (ROOT / 'plans' / 'curricula.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    return out


def build_words(src):
    """Maintainers only. Keeps everyday words: in the public-domain word list, used at least
    8 times across several public-domain novels and essays in src/pg*.txt, and not blocked."""
    import re
    from collections import Counter
    src = Path(src)
    blocked = set()
    for f in ('blocklist_family.sha256', 'blocklist_extra.sha256'):
        blocked |= {l.strip() for l in (src / f).read_text().splitlines() if l.strip() and not l.startswith('#')}
    total, books = Counter(), Counter()
    for f in sorted(src.glob('pg*.txt')):
        c = Counter(re.findall(r"[a-z]+", f.read_text(errors='ignore').lower()))
        total.update(c)
        books.update(set(c))
    words = []
    for w in (src / 'typing_words_source.txt').read_text().split():
        if w.isalpha() and w.islower() and w.isascii() and 2 <= len(w) <= 7:
            if total[w] >= 8 and books[w] >= 2 and hashlib.sha256(w.encode()).hexdigest() not in blocked:
                words.append(w)
    (ROOT / 'data' / 'typing_words.txt').write_text('\n'.join(sorted(set(words))) + '\n')
    return len(words)


if __name__ == '__main__':
    out = build_curricula()
    print('curricula:', len(out['skills']), 'skills,', sum(len(s['stages']) for s in out['skills']), 'stages')
    if '--words' in sys.argv:
        print('typing words:', build_words(sys.argv[sys.argv.index('--words') + 1]))
