"""Offline checks for Skill a Day. Run: python3 tests/test_skilladay.py"""
import datetime as dt
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import skilladay as L  # noqa: E402

PLAN = json.loads((ROOT / 'plans' / 'curricula.json').read_text())
SKILLS = {s['id']: s for s in PLAN['skills']}
HOSTS = {'www.gutenberg.org', 'en.wikipedia.org', 'lichess.org', 'handbook.fide.com', 'support.google.com',
         'support.microsoft.com', 'help.libreoffice.org'}
PD_BOOKS = {'14264', '16317', '13510', '33870'}  # all first published 1913 to 1921, public domain in the US
NO_CREDIT = ['gutenberg', 'wikipedia', 'lichess', 'fide', 'carnegie', 'esenwein', 'verrill', 'capablanca',
             'wikimedia', 'creative commons', 'harold speed', 'hyatt']
DASHES = ('\u2014', '\u2013')


def texts(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k not in ('url', 'link', 'id'):
                yield from texts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from texts(v)


class Curricula(unittest.TestCase):
    def test_menu(self):
        self.assertEqual(PLAN['menu'], ['typing', 'drawing', 'chess', 'spreadsheets', 'speaking', 'mentalmath', 'knots', 'juggling'])

    def test_shape(self):
        for s in PLAN['skills']:
            for k in ('id', 'name', 'emoji', 'blurb', 'need', 'warmups', 'wrapup', 'measure', 'resources', 'stages'):
                self.assertIn(k, s, s['id'])
            self.assertEqual(len(s['stages']), 6, s['id'])
            self.assertGreaterEqual(len(s['warmups']), 4)
            for st in s['stages']:
                self.assertEqual(len(st['drills']), 6, (s['id'], st['title']))
                for k in ('task', 'record', 'ready_if'):
                    self.assertTrue(st['check'][k])
                self.assertTrue(st['easier'] and st['harder'] and st['goal'])
                titles = [d['title'] for d in st['drills']]
                self.assertEqual(len(titles), len(set(titles)))

    def test_no_dashes(self):
        blob = (ROOT / 'plans' / 'curricula.json').read_text() + (ROOT / 'scripts' / 'curricula.py').read_text()
        for d in DASHES:
            self.assertNotIn(d, blob)

    def test_links_allowed(self):
        urls = set(re.findall(r'https?://[^\s"]+', json.dumps(PLAN)))
        self.assertGreater(len(urls), 30)
        for u in urls:
            self.assertTrue(u.startswith('https://'), u)
            host = u.split('/')[2]
            self.assertIn(host, HOSTS, u)
            if host == 'www.gutenberg.org':
                self.assertIn(u.rsplit('/', 1)[1], PD_BOOKS, u)
            self.assertNotIn('(', u)

    def test_no_third_party_credit_in_text(self):
        for s in PLAN['skills']:
            for t in texts(s):
                low = t.lower()
                for name in NO_CREDIT:
                    self.assertNotRegex(low, r'\b' + name + r'\b', (s['id'], t))

    def test_safety_notes(self):
        self.assertIn('qualified instructor', SKILLS['knots']['safety'])
        for st in range(1, 7):
            t = L.session(SKILLS['knots'], '2026-11-10', 'drill', st, 1, 'X', [])['text']
            self.assertIn('qualified instructor', t)
        self.assertTrue(SKILLS['juggling']['safety'])

    def test_generators(self):
        self.assertEqual({s['generator'] for s in PLAN['skills']}, {'typing', 'math', 'sheets', 'speaking', None})
        words = (ROOT / 'data' / 'typing_words.txt').read_text().split()
        for st in SKILLS['typing']['stages']:
            pool = [w for w in words if set(w) <= set(st['gen']['letters'])]
            self.assertGreaterEqual(len(pool), 20, st['title'])
        for st in SKILLS['mentalmath']['stages']:
            self.assertIn(st['gen']['kind'], ('add2', 'sub2', 'x5_11_25', 'mul21', 'sq_pct', 'mixed'))
        for st in SKILLS['spreadsheets']['stages']:
            self.assertTrue(st['gen']['questions'])
        self.assertEqual(len(PLAN['speaking_topics']), len(set(PLAN['speaking_topics'])))
        self.assertGreaterEqual(len(PLAN['speaking_topics']), 30)


def d(s):
    return dt.date.fromisoformat(s)


class Schedule(unittest.TestCase):
    def test_daily_from_monday(self):
        rows = L.schedule('daily', d('2026-11-09'), 1, 1, 14)
        kinds = [r['kind'] for r in rows]
        self.assertEqual(kinds[:7], ['drill'] * 6 + ['check'])
        self.assertEqual(rows[6]['stage'], 1)
        self.assertEqual((rows[7]['stage'], rows[7]['drill']), (2, 1))
        self.assertEqual(rows[13]['kind'], 'check')

    def test_weekdays(self):
        rows = L.schedule('weekdays', d('2026-11-10'), 1, 1, 14)
        for r in rows:
            wd = d(r['date']).weekday()
            if wd >= 5:
                self.assertEqual(r['kind'], 'off')
            if r['kind'] == 'check':
                self.assertEqual(wd, 4)

    def test_mwf(self):
        rows = L.schedule('mwf', d('2026-11-09'), 1, 1, 14)
        on = [d(r['date']).weekday() for r in rows if r['kind'] != 'off']
        self.assertTrue(set(on) <= {0, 2, 4})
        self.assertIn('check', [r['kind'] for r in rows])

    def test_first_session_never_check(self):
        for pace, start in (('daily', '2026-11-15'), ('weekdays', '2026-11-13'), ('mwf', '2026-11-13')):
            rows = [r for r in L.schedule(pace, d(start), 1, 1, 7) if r['kind'] not in ('off',)]
            self.assertEqual(rows[0]['kind'], 'drill', pace)

    def test_paused(self):
        rows = L.schedule('daily', d('2026-11-09'), 1, 1, 3, paused={'2026-11-10'})
        self.assertEqual([r['kind'] for r in rows], ['drill', 'paused', 'drill'])
        self.assertEqual(rows[2]['drill'], 2)

    def test_keep_going(self):
        rows = L.schedule('daily', d('2026-11-09'), 6, 6, 3)
        self.assertEqual((rows[1]['stage'], rows[1]['drill']), (7, 1))
        self.assertEqual(L.base_stage(7), 4)
        self.assertEqual(L.base_stage(9), 6)
        self.assertEqual(L.base_stage(10), 4)

    def test_after_check(self):
        self.assertEqual(L.after_check(2, 2, 4, 'easy'), {'stage': 3, 'drill': 1, 'tweak': 'harder'})
        self.assertEqual(L.after_check(2, 2, 4, 'hard'), {'stage': 2, 'drill': 1, 'tweak': 'easier'})
        self.assertEqual(L.after_check(2, 2, 4, 'right'), {'stage': 2, 'drill': 4, 'tweak': None})


class Sessions(unittest.TestCase):
    def test_every_session_renders(self):
        for s in PLAN['skills']:
            for stage in range(1, 8):
                for kind in ('drill', 'check'):
                    for drill in (1, 6):
                        out = L.session(s, '2026-11-10', kind, stage, drill, 'SALT', PLAN['speaking_topics'])
                        t = out['text']
                        for dash in DASHES:
                            self.assertNotIn(dash, t)
                        self.assertIn('Warm-up (3 min)', t)
                        self.assertTrue('Practice (10 min)' in t or 'Check (10 min)' in t)
                        if kind == 'drill':
                            self.assertIn('Wrap-up (2 min)', t)
                        if kind == 'check' and s['generator'] in ('math', 'sheets'):
                            self.assertTrue(out['private']['answers'])
                        for a in out['private'].get('answers', []):
                            self.assertNotIn(f'= {a}', t)

    def test_deterministic(self):
        s = SKILLS['typing']
        a = L.session(s, '2026-11-10', 'drill', 3, 2, 'X', [])['text']
        b = L.session(s, '2026-11-10', 'drill', 3, 2, 'X', [])['text']
        c = L.session(s, '2026-11-11', 'drill', 3, 2, 'X', [])['text']
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_typing_letters(self):
        s = SKILLS['typing']
        for n in (1, 2, 3):
            out = L.session(s, '2026-11-10', 'drill', n, 1, 'X', [])
            allowed = set(s['stages'][n - 1]['gen']['letters']) | {' '}
            for line in out['material']['lines']:
                self.assertTrue(set(line) <= allowed, line)

    def test_math_answers(self):
        for kind in ('add2', 'sub2', 'x5_11_25', 'mul21', 'sq_pct', 'mixed'):
            for seed in range(30):
                for p in L.math_problems(kind, f's{seed}', 10):
                    q = p['q']
                    if 'squared' in q:
                        n = int(q.split()[0]); v = n * n
                    elif '%' in q:
                        pct, base = re.match(r'(\d+)% of (\d+)', q).groups(); v = int(pct) * int(base) / 100
                    else:
                        v = eval(q.replace('x', '*'))  # noqa: S307 (digits and operators only)
                    self.assertEqual(v, p['a'], q)
                    self.assertEqual(v, int(v))
                    if '-' in q:
                        self.assertGreater(v, 0)

    def test_sheets_answers(self):
        for st in SKILLS['spreadsheets']['stages']:
            for seed in range(20):
                m = L.sheets_material(st['gen'], f's{seed}')
                head, rows = m['table'][0], m['table'][1:]
                self.assertEqual(len(rows), 12)
                col = {h: i for i, h in enumerate(head)}
                units = [r[col['Units']] for r in rows]
                for q in m['questions']:
                    if q['q'].startswith('What is the total of the Units'):
                        self.assertEqual(q['a'], sum(units))
                    if q['q'].startswith('What is the largest'):
                        self.assertEqual(q['a'], max(units))
                    if 'more than 50 units' in q['q']:
                        self.assertEqual(q['a'], sum(u > 50 for u in units))
                    if 'total revenue' in q['q']:
                        self.assertAlmostEqual(q['a'], round(sum(r[col['Units']] * r[col['Price']] for r in rows), 2))
                if st['gen'].get('price_list'):
                    self.assertNotIn('Price', head)
                    self.assertEqual(len(m['price_list']), 7)

    def test_speaking_topics_no_repeat(self):
        topics = PLAN['speaking_topics']
        start = d('2026-11-10')
        seen = [L.speaking_topic(topics, 'X', (start + dt.timedelta(i)).isoformat()) for i in range(len(topics))]
        self.assertEqual(len(seen), len(set(seen)))


class Grading(unittest.TestCase):
    def test_typing(self):
        self.assertEqual(L.grade_typing('the quick brown fox', 'the quick brown fox', 60)['accuracy_pct'], 100.0)
        g = L.grade_typing('the quick brown fox jumps', 'teh quick brwn fox', 30)
        self.assertLess(g['accuracy_pct'], 100)
        self.assertGreater(g['accuracy_pct'], 70)
        self.assertEqual(g['wpm'], round(len('teh quick brwn fox') / 5 / 0.5, 1))

    def test_answers(self):
        self.assertEqual(L.grade_answers([85, 61, 12], '85, 61, 13')['score'], 2)
        self.assertEqual(L.grade_answers([85, 61], '85 61')['score'], 2)
        self.assertEqual(L.grade_answers([12.5, 'North or West'], '$12.50; west')['score'], 2)
        self.assertEqual(L.grade_answers([1250], '1,250')['score'], 1)
        self.assertEqual(L.grade_answers([5, 6], '1. 5\n2. 6')['score'], 2)


class CustomPlans(unittest.TestCase):
    def sample(self):
        s = json.loads(json.dumps(SKILLS['juggling']))
        s.update({'id': 'pottery', 'name': 'Hand-building pottery', 'blurb': 'Shape clay by hand.', 'source': 'custom',
                  'flags': [], 'generator': None, 'safety': None, 'label': L.CUSTOM_LABEL})
        return s

    def risky(self, name='Rock climbing'):
        s = self.sample(); s['id'] = 'climbing'; s['name'] = name
        s['safety'] = 'This plan covers background, knots on the ground and fitness only. To climb, learn from a qualified instructor.'
        s['scope'] = L.SAFE_SCOPE
        return s

    def test_valid(self):
        self.assertTrue(L.validate(self.sample())['ok'])

    def test_label_required(self):
        s = self.sample(); del s['label']
        self.assertFalse(L.validate(s)['ok'])
        s['label'] = 'Draft plan'
        self.assertFalse(L.validate(s)['ok'])

    def test_dash_rejected(self):
        s = self.sample(); s['blurb'] = 'Clay \u2014 by hand'
        self.assertFalse(L.validate(s)['ok'])

    def test_risky_safe_parts_only(self):
        self.assertTrue(L.validate(self.risky())['ok'])
        s = self.risky(); s['safety'] = None
        self.assertFalse(L.validate(s)['ok'])
        s = self.risky(); s['safety'] = 'Be careful on the wall.'
        self.assertFalse(L.validate(s)['ok'])
        s = self.risky(); del s['scope']
        self.assertFalse(L.validate(s)['ok'])
        s = self.risky(); s['scope'] = 'full'
        self.assertFalse(L.validate(s)['ok'])

    def test_bot_marked_risky(self):
        s = self.sample(); s['risky'] = True
        self.assertFalse(L.validate(s)['ok'])
        s.update({'safety': 'Learn from a qualified instructor before firing a kiln.', 'scope': L.SAFE_SCOPE})
        self.assertTrue(L.validate(s)['ok'])

    def test_risky_terms(self):
        for n in ('Rock climbing', 'Scuba diving', 'Driving', 'Skiing', 'Day trading', 'Home electrical wiring', 'Skateboarding'):
            self.assertTrue(L.validate(self.risky(n))['risky'], n)
        for n in ('Hand-building pottery', 'Lawn care', 'Taxidermy basics', 'Sketching skills', 'Calligraphy'):
            s = self.sample(); s['name'] = n
            self.assertFalse(L.validate(s)['risky'], n)

    def test_custom_sessions_carry_label_and_safety(self):
        s = self.risky()
        for kind, drill in (('drill', 1), ('check', 1)):
            t = L.session(s, '2026-11-10', kind, 2, drill, 'X', [])['text']
            self.assertIn(L.CUSTOM_LABEL, t)
            self.assertIn('safe parts only', t)
            self.assertIn('qualified instructor', t)
        t = L.session(SKILLS['juggling'], '2026-11-10', 'drill', 2, 1, 'X', [])['text']
        self.assertNotIn(L.CUSTOM_LABEL, t)

    def test_flags_required(self):
        s = self.sample(); del s['flags']
        self.assertFalse(L.validate(s)['ok'])

    def test_wrong_shape(self):
        s = self.sample(); s['stages'] = s['stages'][:5]
        self.assertFalse(L.validate(s)['ok'])


class Naming(unittest.TestCase):
    def test_name_and_slug(self):
        readme = (ROOT / 'README.md').read_text()
        self.assertIn('Skill a Day', readme)
        self.assertIn('Play-Omega-Games/skill-a-day', readme)
        self.assertEqual(PLAN['meta']['name'], 'Skill a Day: curricula')
        for f in ROOT.rglob('*'):
            if f.is_file() and '.git' not in f.parts and f.suffix in ('.py', '.md', '.json', '.txt'):
                low = f.read_text(errors='ignore').lower()
                for old in ('learn' + ' a skill', 'learn' + '-a-skill', 'learn' + 'skill'):
                    self.assertNotIn(old, low, f)


class LiveTestFixes(unittest.TestCase):
    def test_one_day_lookup_checks_same_stage_as_projection(self):
        proj = L.schedule('weekdays', dt.date(2026, 11, 2), 1, 1, 14)
        fri = [x for x in proj if x['date'] == '2026-11-13'][0]
        one = L.schedule('weekdays', dt.date(2026, 11, 13), 2, 3, 1, done_since_check=4)[0]
        self.assertEqual((fri['kind'], fri['stage']), ('check', 1))
        self.assertEqual((one['kind'], one['stage']), ('check', 1))

    def test_start_mid_plan_checks_own_stage(self):
        out = L.schedule('mwf', dt.date(2026, 11, 4), 3, 1, 3)
        self.assertEqual(out[-1], {'date': '2026-11-06', 'kind': 'check', 'stage': 3})

    def test_easy_never_moves_back(self):
        self.assertEqual(L.after_check(1, 2, 3, 'easy'), {'stage': 2, 'drill': 3, 'tweak': 'harder'})
        self.assertEqual(L.after_check(1, 1, 5, 'easy'), {'stage': 2, 'drill': 1, 'tweak': 'harder'})

    def test_grading_reads_natural_replies(self):
        exp = [53, 60, 52, 79, 112, 77, 33, 105]
        for reply in ('53, 60, 52, 79, 112, 77, 33, 105 (about 4 min)',
                      '53 60 52 79 112 77 33 105, 4 minutes',
                      '1. 53\n2. 60\n3. 52\n4. 79\n5. 112\n6. 77\n7. 33\n8. 105',
                      '53, 60, 52, 79, 112, 77, 33, 105. Took me about 4 minutes',
                      '53,60,52,79,112,77,33,105'):
            self.assertEqual(L.grade_answers(exp, reply)['score'], 8, reply)
        self.assertEqual(L.grade_answers([2400, 420], '2,400, 420')['score'], 2)
        self.assertEqual(L.grade_answers(['Water bottle', 2, 13517.75], 'Water bottle; 2; 13517.75 (took 6 minutes)')['score'], 3)

    def test_validator_keeps_parentheses_in_links(self):
        plan = {'resources': [{'url': 'https://en.wikipedia.org/wiki/Grade_(climbing)'}],
                'stages': [{'drills': [{'do': 'See it (https://en.wikipedia.org/wiki/Bouldering).'}]}]}
        found = re.findall(r'https?://(?:[^\s"()]|\([^\s"()]*\))+', json.dumps(plan))
        self.assertIn('https://en.wikipedia.org/wiki/Grade_(climbing)', found)
        self.assertIn('https://en.wikipedia.org/wiki/Bouldering', found)
        res = L.validate(plan)
        self.assertNotIn('link is not https: https://en.wikipedia.org/wiki/Grade_(climbing', ' '.join(res['errors']))


if __name__ == '__main__':
    unittest.main(verbosity=1)
