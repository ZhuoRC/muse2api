"""Importing under an existing label is a re-login: cookies are replaced, no duplicate account."""
import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
home = tempfile.TemporaryDirectory()
os.environ.update(MUSE2API_HOME=home.name, MUSE2API_PROFILE_ROOT=home.name, MUSE2API_KEY='test-only')
import app

first = app.add_account(app.AccountRequest(label='a@example.com', cookies={'hatch_sess': 'old'},
                                           expires={'hatch_vml': 4102444800}))
aid = first['added'][0]['id']
assert first['added'][0]['replaced'] is False
app.store.update_account(aid, ok=False, enabled=False, use_count=7)

again = app.add_account(app.AccountRequest(label='a@example.com', cookies={'hatch_sess': 'new'}))
row = again['added'][0]
assert row['id'] == aid and row['replaced'] is True and row['enabled'] is False
acc = app.store.get_account(aid)
assert acc['cookies'] == {'hatch_sess': 'new'}
assert acc['ok'] is None and acc['use_count'] == 7 and acc['enabled'] is False
assert 'hatch_vml' not in acc['cookies_exp']
assert len(app.store.accounts) == 1

other = app.add_account(app.AccountRequest(label='b@example.com', cookies={'hatch_sess': 'x'}))
assert other['added'][0]['replaced'] is False and len(app.store.accounts) == 2

blank = app.add_account(app.AccountRequest(cookies={'hatch_sess': 'y'}))
assert blank['added'][0]['replaced'] is False and len(app.store.accounts) == 3

task = app.store.create_task('video', 'p')
app.store.update_task(task['id'], status='completed', account=aid, url='/v1/media/x.mp4')
assert app.get_video(task['id'])['account_label'] == 'a@example.com'

app.MANAGED_DEPLOYMENT = True
import asyncio
try:
    asyncio.run(app.admin_repo_push({}))
    raise AssertionError('repo push must be refused on a managed deployment')
except app.HTTPException as exc:
    assert exc.status_code == 409
print('PASS: same label replaces cookies and keeps enabled/use_count, other labels add, video task names its account, managed deployment refuses repo push')
home.cleanup()
