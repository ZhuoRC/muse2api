"""next_keepalive_at agrees with keepalive_needed; import with verify tests the account in the background."""
import os, sys, tempfile, time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
home = tempfile.TemporaryDirectory()
os.environ.update(MUSE2API_HOME=home.name, MUSE2API_PROFILE_ROOT=home.name, MUSE2API_KEY='test-only')
import app

H = 3600
now = 1_800_000_000
tick = now + 300
I = app.KEEPALIVE_INTERVAL_SECONDS


def nxt(**a):
    return app.next_keepalive_at({"enabled": True, **a}, now, tick)


assert nxt() == tick
assert app.next_keepalive_at({"enabled": False, "last_keepalive": now}, now, tick) is None
assert app.next_keepalive_at({"enabled": True}, now, None) == now

fresh = nxt(last_keepalive=now - H, ok=True, expires_at=now + 5 * 24 * H)
assert fresh >= now + 5 * 24 * H - 36 * H and (fresh - tick) % I == 0

bad = nxt(last_keepalive=now - H, ok=False, expires_at=now + 5 * 24 * H)
assert now + 5 * H < bad <= now + 5 * H + I and (bad - tick) % I == 0

due = nxt(last_keepalive=now - 7 * H, ok=True, expires_at=now + 10 * H)
assert due == tick

for acc in ({"last_keepalive": now - H, "ok": True, "expires_at": now + 5 * 24 * H},
            {"last_keepalive": now - H, "ok": False, "expires_at": now + 5 * 24 * H},
            {"last_keepalive": now - 2 * H, "ok": True, "expires_at": now + 30 * H}):
    at = nxt(**acc)
    assert app.keepalive_needed(acc, at), (acc, at)
    assert not app.keepalive_needed(acc, at - I), (acc, at)

calls = []


def fake_test(aid):
    calls.append(aid)
    app.store.mark(aid, True, "会话有效")
    return {"ok": True, "message": "会话有效，可正常生成", "quota": {"plan": "Free plan"}, "quota_error": None}


with patch.object(app, "_test_account_sync", side_effect=fake_test):
    r = app.add_account(app.AccountRequest(label='v@example.com', cookies={'hatch_sess': 's'}, verify=True))
    row = r['added'][0]
    assert row['verify'] == 'running'
    for _ in range(50):
        v = app.store.get_account(row['id']).get('verify') or {}
        if v.get('status') == 'done':
            break
        time.sleep(0.05)
    assert v == {**v, 'status': 'done', 'ok': True} and calls == [row['id']]

plain = app.add_account(app.AccountRequest(label='p@example.com', cookies={'hatch_sess': 's'}))
assert 'verify' not in plain['added'][0]

listed = app.list_accounts()
assert all('next_keepalive_at' in a for a in listed['accounts'])
assert listed['keepalive']['interval'] == I
print('PASS: next keep-alive time matches keepalive_needed, disabled accounts have none, verify=True tests in background and records the result')
home.cleanup()
