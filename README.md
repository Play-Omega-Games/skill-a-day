# Skill a Day

Practice library for the 🌱 Skill a Day Grok Bot template by Omega Games: 15 minutes a day (3 minutes of warm-up, 10 of practice, 2 to wrap up), a weekly progress check and a level that adjusts.

Eight skills, each with 6 stages of 6 drills plus a weekly check: touch typing, drawing basics, chess, spreadsheets, public speaking, mental math, knots and juggling. Typing lines, math sets, spreadsheet practice tables and speaking topics are made fresh each day by code, and answers are checked by code.

## Quick start

```
python3 scripts/skilladay.py menu
python3 scripts/skilladay.py schedule --skill chess --pace weekdays --from 2026-11-10 --days 14
python3 scripts/skilladay.py session --skill mentalmath --date 2026-11-10 --kind drill --stage 1 --drill 1 --salt demo
python3 tests/test_skilladay.py
python3 scripts/check_links.py
```

A bot loads every file listed in `MANIFEST.txt` from `https://raw.githubusercontent.com/Play-Omega-Games/skill-a-day/main/` and checks each SHA-256.

## Files

- `scripts/curricula.py`: the curricula, in Omega Games' own words. `scripts/build.py` writes `plans/curricula.json` from it.
- `plans/curricula.json`: the built curricula the bot reads.
- `scripts/skilladay.py`: dated schedules, sessions, practice material, grading, level changes and validation of custom plans (standard library only).
- `scripts/check_links.py`: checks every link live.
- `data/typing_words.txt`: everyday words for typing drills.
- `tests/test_skilladay.py`: offline checks.

## Custom skills

For a skill that isn't on the menu, the bot drafts a plan in the same shape, flags anything it can't verify, and runs `skilladay.py validate <plan> --live` before using it. Every custom plan carries the label "Draft plan written by your bot, not reviewed by Omega Games". A skill that can hurt someone or carries money, legal or health stakes gets a plan for the safe parts only, with a note to learn from a qualified instructor; the validator rejects a risky plan without both.

## License

Content is CC0 1.0. Code is MIT. See `LICENSE`.

Questions or ideas? Contact Omega Games at john@playomega.games.
