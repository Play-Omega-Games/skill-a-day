"""Skill a Day engine: dated schedules, daily sessions, practice material and grading.
Standard library only. Run from anywhere; data paths are relative to the repo root.

    python3 scripts/skilladay.py menu
    python3 scripts/skilladay.py schedule --skill typing --pace daily --from 2026-11-10 --stage 1 --drill 1 --days 14
    python3 scripts/skilladay.py session --skill typing --date 2026-11-10 --kind drill --stage 1 --drill 1 --salt abc
    python3 scripts/skilladay.py grade-typing --target-file t.txt --typed-file y.txt --seconds 60
    python3 scripts/skilladay.py grade --skill mentalmath --date 2026-11-10 --kind drill --stage 1 --salt abc --answers "85, 61"
    python3 scripts/skilladay.py validate custom/pottery.json [--live]
"""
import argparse
import datetime as dt
import difflib
import hashlib
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / 'plans' / 'curricula.json'
WORDS = ROOT / 'data' / 'typing_words.txt'
PACES = {'daily': {0, 1, 2, 3, 4, 5, 6}, 'weekdays': {0, 1, 2, 3, 4}, 'mwf': {0, 2, 4}}
CHECK_DAY = {'daily': 6, 'weekdays': 4, 'mwf': 4}
PACE_LABEL = {'daily': 'Every day', 'weekdays': 'Weekdays only', 'mwf': 'Mon, Wed and Fri'}
DASHES = ('\u2014', '\u2013')
CUSTOM_LABEL = 'Draft plan written by your bot, not reviewed by Omega Games'
INSTRUCTOR_NOTE = 'learn from a qualified instructor'
SAFE_SCOPE = 'safe parts only'


# ------------------------------------------------------------------ loading
def load_plan():
    return json.loads(PLAN.read_text())


def get_skill(skill_id, custom=None):
    if custom:
        return json.loads(Path(custom).read_text())
    for s in load_plan()['skills']:
        if s['id'] == skill_id:
            return s
    raise SystemExit(f'unknown skill {skill_id}')


def rng_for(*parts):
    h = hashlib.sha256('|'.join(str(p) for p in parts).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def base_stage(stage):
    """Stages 7 and up are 'keep going' rounds that replay stages 4 to 6, harder."""
    return stage if stage <= 6 else 4 + (stage - 7) % 3


def advance(stage, drill):
    drill += 1
    if drill > 6:
        return stage + 1, 1
    return stage, drill


# ------------------------------------------------------------------ schedule
def schedule(pace, start, stage, drill, days, paused=(), done_since_check=0, check_day=None):
    """Dated sessions from `start`, assuming each weekly check is answered 'About right'."""
    practice = PACES[pace]
    cday = CHECK_DAY[pace] if check_day is None else check_day
    out = []
    last_stage, last_drill, first_stage = stage, drill - 1, stage
    d = start
    for _ in range(days):
        iso = d.isoformat()
        if d.weekday() not in practice:
            out.append({'date': iso, 'kind': 'off'})
        elif iso in paused:
            out.append({'date': iso, 'kind': 'paused'})
        elif d.weekday() == cday and done_since_check > 0:
            # Check the stage just finished if the new one has barely started.
            checked = last_stage - 1 if (last_drill < 3 and last_stage - 1 >= first_stage) else last_stage
            out.append({'date': iso, 'kind': 'check', 'stage': checked})
            done_since_check = 0
        else:
            out.append({'date': iso, 'kind': 'drill', 'stage': stage, 'drill': drill})
            last_stage, last_drill = stage, drill
            done_since_check += 1
            stage, drill = advance(stage, drill)
        d += dt.timedelta(days=1)
    return out


def after_check(checked_stage, stage, drill, result):
    """New position and tweak after a weekly check.
    checked_stage: the stage that was checked. (stage, drill): the next drill not yet done.
    result 'easy': move to the stage after the checked one, with the harder tweak on next week.
    result 'hard': restart the checked stage at drill 1, with the easier tweak on next week.
    result 'right': carry on, no tweak."""
    if result == 'easy':
        return {'stage': checked_stage + 1, 'drill': 1, 'tweak': 'harder'}
    if result == 'hard':
        return {'stage': checked_stage, 'drill': 1, 'tweak': 'easier'}
    return {'stage': stage, 'drill': drill, 'tweak': None}


# ------------------------------------------------------------------ generators
def _words():
    return WORDS.read_text().split()


def typing_material(gen, prev_letters, seed, lines=5, per_line=8, passage_words=0):
    r = rng_for(seed, 'typing')
    allowed = set(gen['letters'])
    new = allowed - set(prev_letters or '')
    pool = [w for w in _words() if set(w) <= allowed]
    focus = [w for w in pool if set(w) & new] if new and prev_letters else pool
    def pick(n):
        out = []
        for _ in range(n):
            src = focus if (focus and r.random() < 0.6) else pool
            out.append(r.choice(src))
        return out
    def dress(ws):
        ws = list(ws)
        if gen.get('numbers'):
            for _ in range(2):
                ws.insert(r.randrange(len(ws) + 1), str(r.choice([3, 7, 12, 25, 48, 60, 105, 2026, 365, 19])))
        text = ' '.join(ws)
        if gen.get('caps') or gen.get('punct'):
            parts = re.split(r'(?<=\S) (?=\S)', text)
            sent, out, n = [], [], r.randint(4, 7)
            for p in parts:
                sent.append(p)
                if len(sent) >= n:
                    out.append(sent); sent = []; n = r.randint(4, 7)
            if sent:
                out.append(sent)
            rendered = []
            for s in out:
                s = s[:]
                if gen.get('caps'):
                    s[0] = s[0][:1].upper() + s[0][1:]
                if gen.get('punct') and len(s) > 3 and r.random() < 0.5:
                    s[1] = s[1] + ','
                end = r.choice(['.', '.', '?', '.']) if gen.get('punct') else ''
                rendered.append(' '.join(s) + end)
            text = ' '.join(rendered)
        return text
    if passage_words:
        return {'passage': dress(pick(passage_words))}
    return {'lines': [dress(pick(per_line)) for _ in range(lines)]}


def math_problems(kind, seed, n):
    r = rng_for(seed, 'math', kind)
    kinds = ['add2', 'sub2', 'x5_11_25', 'mul21', 'sq_pct'] if kind == 'mixed' else [kind]
    probs = []
    seen = set()
    while len(probs) < n:
        k = r.choice(kinds)
        if k == 'add2':
            a, b = r.randint(12, 89), r.randint(12, 89); q, ans = f'{a} + {b}', a + b
        elif k == 'sub2':
            if r.random() < 0.35:
                a = r.randint(11, 89); q, ans = f'100 - {a}', 100 - a
            else:
                a = r.randint(41, 99); b = r.randint(12, a - 5); q, ans = f'{a} - {b}', a - b
        elif k == 'x5_11_25':
            m = r.choice([5, 11, 25])
            a = r.randint(12, 98) if m == 11 else r.choice(range(4, 120, 2)) if m == 25 else r.randint(12, 198)
            if m == 25 and a % 4:
                a = a - a % 4 or 4
            q, ans = f'{a} x {m}', a * m
        elif k == 'mul21':
            a, b = r.randint(12, 99), r.randint(3, 9); q, ans = f'{a} x {b}', a * b
        else:
            t = r.random()
            if t < 0.3:
                a = r.choice([15, 25, 35, 45, 55, 65, 75, 85, 95]); q, ans = f'{a} squared', a * a
            elif t < 0.5:
                a = r.randint(11, 30); q, ans = f'{a} squared', a * a
            else:
                p = r.choice([10, 15, 20])
                base = r.choice(range(20, 1001, 20)); q, ans = f'{p}% of {base}', base * p // 100
        if q in seen:
            continue
        seen.add(q)
        probs.append({'q': q, 'a': ans})
    return probs


ITEMS = ['Notebook', 'Pen set', 'Mug', 'Backpack', 'Desk lamp', 'Water bottle', 'Planner', 'Tote bag']
REGIONS = ['North', 'South', 'East', 'West']


def sheets_material(gen, seed):
    r = rng_for(seed, 'sheets')
    items = r.sample(ITEMS, 6)
    prices = {i: round(r.choice(range(300, 4000, 25)) / 100, 2) for i in items}
    year = 2025
    rows = []
    for m in range(1, 13):
        it = r.choice(items)
        rows.append({'Date': f'{year}-{m:02d}-{r.randint(1, 28):02d}', 'Item': it, 'Region': r.choice(REGIONS),
                     'Units': r.randint(5, 95), 'Price': prices[it]})
    lookup = bool(gen.get('price_list'))
    cols = ['Date', 'Item', 'Region', 'Units'] + ([] if lookup else ['Price'])
    qs = []
    region = r.choice(sorted({x['Region'] for x in rows}))
    item_in = r.choice(sorted({x['Item'] for x in rows}))
    thresh = 50
    def rev():
        return round(sum(x['Units'] * x['Price'] for x in rows), 2)
    by_region = {g: sum(x['Units'] for x in rows if x['Region'] == g) for g in REGIONS}
    by_item = {}
    for x in rows:
        by_item[x['Item']] = by_item.get(x['Item'], 0) + x['Units']
    for key in gen.get('questions', []):
        if key == 'total_units':
            qs.append({'q': 'What is the total of the Units column?', 'a': sum(x['Units'] for x in rows)})
        elif key == 'avg_price':
            qs.append({'q': 'What is the average of the Price column, to two decimals?', 'a': round(sum(x['Price'] for x in rows) / 12, 2)})
        elif key == 'max_units':
            qs.append({'q': 'What is the largest number in the Units column?', 'a': max(x['Units'] for x in rows)})
        elif key == 'min_units':
            qs.append({'q': 'What is the smallest number in the Units column?', 'a': min(x['Units'] for x in rows)})
        elif key == 'top_item_by_units':
            top = max(by_item.values())
            names = sorted(k for k, v in by_item.items() if v == top)
            qs.append({'q': 'Which item sold the most units in total?', 'a': ' or '.join(names)})
        elif key == 'count_region':
            qs.append({'q': f'How many rows are for the {region} region?', 'a': sum(1 for x in rows if x['Region'] == region)})
        elif key == 'total_revenue':
            qs.append({'q': 'What is the total revenue (Units times Price, added up), to two decimals?', 'a': rev()})
        elif key == 'sum_units_region':
            qs.append({'q': f'What is the total of Units for the {region} region?', 'a': by_region[region]})
        elif key == 'count_units_over':
            qs.append({'q': f'How many rows have more than {thresh} units?', 'a': sum(1 for x in rows if x['Units'] > thresh)})
        elif key == 'top_region_by_units':
            top = max(by_region.values())
            names = sorted(k for k, v in by_region.items() if v == top)
            qs.append({'q': 'Which region sold the most units in total?', 'a': ' or '.join(names)})
        elif key == 'lookup_price':
            qs.append({'q': f'Using the price list, what is the price of {item_in}?', 'a': prices[item_in]})
        elif key == 'lookup_units_first':
            first = next(x for x in rows if x['Item'] == item_in)
            qs.append({'q': f'Using a lookup on the sales table, how many units are on the first row for {item_in}?', 'a': first['Units']})
    table = [cols] + [[x[c] for c in cols] for x in rows]
    out = {'table': table, 'questions': qs}
    if lookup:
        out['price_list'] = [['Item', 'Price']] + [[i, prices[i]] for i in items]
    return out


def speaking_topic(topics, salt, date):
    order = list(range(len(topics)))
    rng_for(salt, 'topics').shuffle(order)
    n = dt.date.fromisoformat(date).toordinal()
    return topics[order[n % len(order)]]


# ------------------------------------------------------------------ session
def md_table(rows):
    head = '| ' + ' | '.join(str(c) for c in rows[0]) + ' |'
    sep = '|' + '---|' * len(rows[0])
    body = ['| ' + ' | '.join(f'{c:.2f}' if isinstance(c, float) else str(c) for c in r) + ' |' for r in rows[1:]]
    return '\n'.join([head, sep] + body)


def csv_block(rows):
    return '\n'.join(','.join(f'{c:.2f}' if isinstance(c, float) else str(c) for c in r) for r in rows)


def session(skill, date, kind, stage, drill, salt, topics=None):
    st_no = base_stage(stage)
    st = skill['stages'][st_no - 1]
    keep_going = stage > 6
    seed = f'{salt}|{date}|{skill["id"]}|{stage}|{kind}'
    warm = skill['warmups'][dt.date.fromisoformat(date).toordinal() % len(skill['warmups'])]
    prev_letters = skill['stages'][st_no - 2]['gen'].get('letters') if st_no > 1 else ''
    gen = st.get('gen') or {}
    out = {'skill': skill['id'], 'date': date, 'kind': kind, 'stage': stage, 'base_stage': st_no,
           'level': st.get('level'), 'stage_title': st['title'], 'keep_going': keep_going, 'private': {}}
    L = []
    head = f"{skill.get('emoji', '')} {skill['name']}: stage {st_no} of 6, {st['title']}".strip()
    if keep_going:
        head += ' (keep-going round, harder)'
    L.append(f'**{head}**')
    if skill.get('source') == 'custom' and (kind == 'check' or drill == 1):
        L.append(f'{CUSTOM_LABEL}.')
        if skill.get('scope') == SAFE_SCOPE:
            L.append('This plan covers the safe parts only.')
    if skill.get('safety') and (kind == 'check' or drill == 1):
        L.append(f"Safety first: {skill['safety']}")
    material = {}
    gname = skill.get('generator')
    if gname == 'typing':
        material = typing_material(gen, prev_letters, seed, passage_words=100 if kind == 'check' else 0)
    elif gname == 'math':
        material = {'problems': math_problems(gen['kind'], seed, 10 if kind == 'check' else 8)}
    elif gname == 'sheets':
        material = sheets_material(gen, seed)
    elif gname == 'speaking':
        material = {'topic': speaking_topic(topics or [], salt, date)}
    if kind == 'check':
        c = st['check']
        L.append('Weekly check, about 15 minutes.')
        L.append(f"Warm-up (3 min): {warm}")
        L.append(f"Check (10 min): {c['task']}")
        L.append(f"Record: {c['record']}. You're ready to move on if: {c['ready_if']}")
    else:
        d = st['drills'][drill - 1]
        out['drill'] = drill
        out['drill_title'] = d['title']
        L.append(f"Session {drill} of 6 this stage. Goal: {st['goal']}")
        L.append(f"Warm-up (3 min): {warm}")
        L.append(f"Practice (10 min), {d['title']}: {d['do']}")
        if d.get('link'):
            L.append(f"See it: {d['link']}")
    if 'lines' in material:
        L.append("Today's lines:\n" + '\n'.join(f'{i}. {t}' for i, t in enumerate(material['lines'], 1)))
    if 'passage' in material:
        L.append('Check passage:\n' + material['passage'])
        out['private']['target'] = material['passage']
    if 'problems' in material:
        L.append("Today's set:\n" + '\n'.join(f"{i}. {p['q']}" for i, p in enumerate(material['problems'], 1)))
        out['private']['answers'] = [p['a'] for p in material['problems']]
    if 'table' in material:
        L.append("Today's practice table (made-up sample data):\n" + md_table(material['table']))
        if material.get('price_list'):
            L.append('Price list:\n' + md_table(material['price_list']))
        L.append('If the table pastes into a single column, paste this instead and use Split text to columns:\n```\n'
                 + csv_block(material['table']) + '\n```')
        L.append("Questions:\n" + '\n'.join(f"{i}. {q['q']}" for i, q in enumerate(material['questions'], 1)))
        out['private']['answers'] = [q['a'] for q in material['questions']]
    if 'topic' in material:
        L.append(f"Today's topic: {material['topic']}")
    if kind != 'check':
        L.append(f"Wrap-up (2 min): {skill['wrapup']}")
        L.append(f"Too much today? {st['easier']} Too easy? {st['harder']}")
    out['text'] = '\n\n'.join(L)
    out['material'] = {k: v for k, v in material.items() if k not in ('problems', 'questions')}
    if 'problems' in material:
        out['material']['problems'] = [p['q'] for p in material['problems']]
    if 'questions' in material:
        out['material']['questions'] = [q['q'] for q in material['questions']]
    return out


# ------------------------------------------------------------------ grading
def grade_typing(target, typed, seconds):
    typed = typed.strip()
    tgt = target.strip()[:max(len(typed), 1)]
    sm = difflib.SequenceMatcher(None, tgt, typed, autojunk=False)
    matched = sum(b.size for b in sm.get_matching_blocks())
    acc = matched / max(len(tgt), len(typed), 1)
    wpm = (len(typed) / 5) / (seconds / 60) if seconds else 0
    return {'accuracy_pct': round(acc * 100, 1), 'wpm': round(wpm, 1), 'chars_typed': len(typed)}


def _num(s):
    s = s.strip().replace('$', '').replace(',', '')
    try:
        return float(s)
    except ValueError:
        return s.lower()


def grade_answers(expected, given):
    s = given.strip()
    if len(expected) == 1:
        parts = [s]
    else:
        parts = [p for p in re.split(r'\s*[;\n]\s*|,\s+', s) if p.strip()]
        if len(parts) < len(expected):
            alt = [p for p in re.split(r'[,\s]+', s) if p]
            if len(alt) == len(expected):
                parts = alt
    parts = [re.sub(r'^\s*\d+[.)]\s+', '', p) for p in parts]
    res = []
    for i, e in enumerate(expected):
        g = parts[i].strip() if i < len(parts) else ''
        if isinstance(e, str):
            ok = g.lower() in [x.lower() for x in e.split(' or ')]
        else:
            gv = _num(g)
            ok = isinstance(gv, float) and abs(gv - float(e)) < 0.006
        res.append({'n': i + 1, 'given': g, 'expected': e, 'ok': ok})
    return {'score': sum(r['ok'] for r in res), 'out_of': len(expected), 'items': res}


# ------------------------------------------------------------------ custom plans
REQUIRED_SKILL = ['id', 'name', 'blurb', 'need', 'warmups', 'wrapup', 'measure', 'stages']
# Word stems that mark a typed skill as risky or high-stakes. Each is matched from a word start;
# short stems carry their own endings so 'ski' doesn't match 'skill' or 'law' 'lawn'.
RISKY = [r'climb', r'boulder', r'div(e|es|ing)\b', r'scuba', r'snorkel', r'firearm', r'guns?\b', r'shoot', r'archery',
         r'knife', r'knives', r'blade', r'martial', r'karate', r'judo', r'boxing', r'kickbox', r'fight', r'wrestl',
         r'weightlift', r'weight training', r'lifting', r'powerlift', r'driv', r'motorcycl', r'fly(ing)?\b', r'pilot',
         r'paraglid', r'skydiv', r'electric', r'wiring', r'chemis', r'medic', r'first aid', r'cpr\b', r'nurs(e|ing)\b',
         r'swim', r'surf', r'ski(s|ing)?\b', r'snowboard', r'skat(e|es|ing)\b', r'skateboard', r'parkour', r'gymnast', r'acrobat',
         r'weld', r'chainsaw', r'fasting', r'diet', r'supplement', r'trading', r'invest', r'crypto', r'tax(es)?\b',
         r'legal', r'laws?\b', r'horse', r'riding', r'sail', r'kayak', r'canoe', r'hunt', r'foraging', r'mushroom',
         r'fire ?(breath|spin|danc)', r'pyrotechn', r'roofing', r'tree climb']


def validate(plan, live=False):
    errs, warns = [], []
    for k in REQUIRED_SKILL:
        if k not in plan:
            errs.append(f'missing {k}')
    stages = plan.get('stages', [])
    if len(stages) != 6:
        errs.append(f'needs 6 stages, has {len(stages)}')
    for n, st in enumerate(stages, 1):
        for k in ('title', 'goal', 'drills', 'easier', 'harder', 'check'):
            if k not in st:
                errs.append(f'stage {n} missing {k}')
        if len(st.get('drills', [])) != 6:
            errs.append(f'stage {n} needs 6 drills')
        for k in ('task', 'record', 'ready_if'):
            if k not in st.get('check', {}):
                errs.append(f'stage {n} check missing {k}')
    blob = json.dumps(plan, ensure_ascii=False)
    if any(d in blob for d in DASHES):
        errs.append('contains an em or en dash')
    if len(plan.get('warmups', [])) < 2:
        errs.append('needs at least 2 warm-ups')
    if plan.get('source') != 'custom':
        errs.append('source must be "custom"')
    if not isinstance(plan.get('flags', None), list):
        errs.append('flags must be a list (things the bot could not verify), even if empty')
    if plan.get('label') != CUSTOM_LABEL:
        errs.append(f'label must be exactly "{CUSTOM_LABEL}"')
    name = ' '.join(str(plan.get(k) or '') for k in ('id', 'name', 'blurb')).lower()
    risky = sorted({m.group(0) for w in RISKY for m in [re.search(r'\b' + w, name)] if m})
    if risky or plan.get('risky'):
        why = ', '.join(risky) if risky else 'marked risky'
        if INSTRUCTOR_NOTE not in str(plan.get('safety') or '').lower():
            errs.append(f'risky skill ({why}): safety note must say "{INSTRUCTOR_NOTE}"')
        if plan.get('scope') != SAFE_SCOPE:
            errs.append(f'risky skill ({why}): scope must be "{SAFE_SCOPE}" (plan the safe parts only)')
    urls = sorted(set(re.findall(r'https?://[^\s"\)]+', blob)))
    for u in urls:
        if not u.startswith('https://'):
            errs.append(f'link is not https: {u}')
    link_results = {}
    if live and urls:
        sys.path.insert(0, str(ROOT / 'scripts'))
        from check_links import check_url
        for u in urls:
            link_results[u] = check_url(u)
            if not link_results[u]['ok']:
                errs.append(f'link failed live check: {u} ({link_results[u]["status"]})')
    elif urls:
        warns.append('links not live-checked; run with --live')
    return {'ok': not errs, 'errors': errs, 'warnings': warns, 'links': link_results, 'risky_terms': risky,
            'risky': bool(risky or plan.get('risky'))}


# ------------------------------------------------------------------ cli
def main(argv=None):
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('menu')
    s = sub.add_parser('schedule')
    s.add_argument('--skill', required=True); s.add_argument('--pace', choices=PACES, default='daily')
    s.add_argument('--from', dest='start', required=True); s.add_argument('--stage', type=int, default=1)
    s.add_argument('--drill', type=int, default=1); s.add_argument('--days', type=int, default=14)
    s.add_argument('--paused', default=''); s.add_argument('--done-since-check', type=int, default=0)
    se = sub.add_parser('session')
    for a in ('--skill', '--date', '--kind', '--salt'):
        se.add_argument(a, required=True)
    se.add_argument('--stage', type=int, required=True); se.add_argument('--drill', type=int, default=1)
    se.add_argument('--custom'); se.add_argument('--json', action='store_true')
    g = sub.add_parser('grade')
    for a in ('--skill', '--date', '--kind', '--salt', '--answers'):
        g.add_argument(a, required=True)
    g.add_argument('--stage', type=int, required=True)
    gt = sub.add_parser('grade-typing')
    gt.add_argument('--target-file', required=True); gt.add_argument('--typed-file', required=True)
    gt.add_argument('--seconds', type=float, required=True)
    ac = sub.add_parser('after-check')
    ac.add_argument('--checked-stage', type=int, required=True)
    ac.add_argument('--stage', type=int, required=True); ac.add_argument('--drill', type=int, required=True)
    ac.add_argument('--result', choices=['easy', 'right', 'hard'], required=True)
    v = sub.add_parser('validate'); v.add_argument('file'); v.add_argument('--live', action='store_true')
    a = p.parse_args(argv)

    if a.cmd == 'menu':
        plan = load_plan()
        for sk in plan['skills']:
            print(f"{sk['id']}\t{sk['emoji']} {sk['name']}\t{sk['blurb']}")
    elif a.cmd == 'schedule':
        rows = schedule(a.pace, dt.date.fromisoformat(a.start), a.stage, a.drill, a.days,
                        set(x for x in a.paused.split(',') if x), a.done_since_check)
        print(json.dumps(rows, indent=1))
    elif a.cmd == 'session':
        sk = get_skill(a.skill, a.custom)
        out = session(sk, a.date, a.kind, a.stage, a.drill, a.salt, load_plan()['speaking_topics'])
        print(json.dumps(out, ensure_ascii=False, indent=1) if a.json else out['text'])
    elif a.cmd == 'grade':
        sk = get_skill(a.skill)
        out = session(sk, a.date, a.kind, a.stage, 1, a.salt, [])
        print(json.dumps(grade_answers(out['private']['answers'], a.answers), indent=1))
    elif a.cmd == 'grade-typing':
        print(json.dumps(grade_typing(Path(a.target_file).read_text(), Path(a.typed_file).read_text(), a.seconds)))
    elif a.cmd == 'after-check':
        print(json.dumps(after_check(a.checked_stage, a.stage, a.drill, a.result)))
    elif a.cmd == 'validate':
        res = validate(json.loads(Path(a.file).read_text()), a.live)
        print(json.dumps(res, indent=1))
        sys.exit(0 if res['ok'] else 1)


if __name__ == '__main__':
    main()
