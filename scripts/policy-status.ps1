param()
. "$PSScriptRoot/common.ps1"
$probe = @'
import json, os, sqlite3, time
from datetime import datetime, timezone
from pathlib import Path
period = datetime.now(timezone.utc).strftime('%Y-%m')
config = json.loads(Path('/app/policy.json').read_text())
path = Path('/app/policy-data/budget.sqlite3')
with sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True) as db:
    row = db.execute('SELECT debit FROM months WHERE period=?', (period,)).fetchone()
    active = db.execute('SELECT count(*) FROM requests WHERE active=1 AND expires>=?', (time.time(),)).fetchone()[0]
    attempts = db.execute('SELECT provider,model,outcome,count(*) FROM attempts GROUP BY provider,model,outcome').fetchall()
print(json.dumps({'period_utc': period, 'monthly_limit_usd': os.environ.get('GATEWAY_MONTHLY_BUDGET_USD','0'), 'conservative_debit_usd': (row[0] if row else 0)/1000000, 'active_requests': active, 'attempt_counts_all_periods': attempts, 'ledger_bytes': path.stat().st_size, 'decision_plane': config['decision_plane'], 'jev_live': 'disabled'}, indent=2))
'@
Invoke-CoreCompose -Arguments @('exec','-T','litellm','python','-c',$probe)
