#!/usr/bin/env python3
"""
Hold back any state a scheduled rebuild made worse, before it is committed.

The rebuild workflow runs every builder unattended, and a builder can come back with less
than it should for reasons that are not the agency's: a feed that answered half a page, a
host that timed out during the video sample, a website that changed shape mid-run. Shipping
that would trade a stale map for a broken one. So after the builders run, each state is
compared with what is committed, and the committed version is put back when:

  - the state file is missing or does not parse,
  - the camera count fell by more than MAX_DROP (a real agency rarely removes a tenth of
    its cameras in a week; Alabama dropped 33 of 629 when it renumbered, about 5%),
  - the state had live video and the rebuild says it has none.

How a locked state's video is played (`relay`, `sign`) is decided by hand and most builders
rewrite the index entry without it, so those fields are always carried over from the
committed index, the same rule as eccf4aa.

Run from the repo root after the builders and before `git add states`:
    python3 scripts/rebuild_guard.py
"""
import json, os, subprocess

MAX_DROP = 0.10
KEEP = ('relay', 'sign')


def committed(path):
    out = subprocess.run(['git', 'show', f'HEAD:{path}'], capture_output=True, text=True)
    return out.stdout if out.returncode == 0 else None


def main():
    old_index = json.loads(committed('states/index.json'))
    new_index = json.load(open('states/index.json'))
    held, notes = [], []

    for code in sorted(set(old_index) | set(new_index)):
        old, new = old_index.get(code), new_index.get(code)
        if old is None:
            notes.append(f'{code}: new state, {new["count"]} cameras')
            continue
        reason = None
        if new is None:
            reason = 'dropped from the index'
        else:
            try:
                json.load(open(new['file']))
            except Exception as e:
                reason = f'state file unreadable ({type(e).__name__})'
        if not reason and new['count'] < old['count'] * (1 - MAX_DROP):
            reason = f'count fell {old["count"]} to {new["count"]}'
        if not reason and old.get('video') and not new.get('video'):
            reason = 'lost its live video'
        if reason:
            text = committed(old['file'])
            if text is not None:
                open(old['file'], 'w').write(text)
            new_index[code] = old
            held.append(f'{code}: held at the committed version, {reason}')
            continue
        for k in KEEP:
            if k in old and new.get(k) != old[k]:
                new[k] = old[k]
        if new['count'] != old['count']:
            notes.append(f'{code}: {old["count"]} to {new["count"]} cameras')

    json.dump(new_index, open('states/index.json', 'w'), indent=1)
    lines = held + notes or ['no state changed its camera count']
    print('\n'.join(lines))
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as f:
            f.write('### Rebuild\n\n' + '\n'.join(f'- {l}' for l in lines) + '\n')
    with open(os.environ.get('REBUILD_NOTES', os.devnull), 'w') as f:
        f.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
