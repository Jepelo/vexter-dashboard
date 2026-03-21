"""
Vexter Dashboard – PowerOffice datafetcher
"""
import requests
import json
import os
import sys
from datetime import datetime

APP_KEY    = os.environ.get('PO_APP_KEY', '')
CLIENT_KEY = os.environ.get('PO_CLIENT_KEY', '')
SUB_KEY    = os.environ.get('PO_SUB_KEY', '')

PO_AUTH = 'https://goapi.poweroffice.net/OAuth/Token'

if not all([APP_KEY, CLIENT_KEY, SUB_KEY]):
    print('FEIL: Mangler nøkler')
    sys.exit(1)

# 1. Token
print('Henter token...')
token_resp = requests.post(
    PO_AUTH,
    headers={
        'Content-Type': 'application/x-www-form-urlencoded',
        'Ocp-Apim-Subscription-Key': SUB_KEY
    },
    data={'grant_type': 'client_credentials'},
    auth=(APP_KEY, CLIENT_KEY),
    timeout=30
)
if not token_resp.ok:
    print(f'Token-feil: {token_resp.status_code} {token_resp.text[:300]}')
    sys.exit(1)
token = token_resp.json()['access_token']
print('Token OK')

hdrs = {
    'Authorization': f'Bearer {token}',
    'Ocp-Apim-Subscription-Key': SUB_KEY
}

# 2. Finn riktig basis-URL
for base in ['https://goapi.poweroffice.net/v2', 'https://goapi.poweroffice.net']:
    r = requests.get(f'{base}/Customer?pageSize=1', headers=hdrs, timeout=15)
    print(f'Test {base}/Customer -> {r.status_code}')
    if r.ok:
        PO_BASE = base
        print(f'Bruker base: {PO_BASE}')
        break
else:
    print('Fant ikke riktig basis-URL!')
    sys.exit(1)

# 3. Hent kunder
customers = []
r = requests.get(f'{PO_BASE}/Customer?pageSize=1000', headers=hdrs, timeout=30)
if r.ok:
    customers = r.json().get('data', [])
    print(f'Kunder: {len(customers)}')

# 4. Hent fakturaer
all_invoices = []
page = 1
while True:
    r = requests.get(f'{PO_BASE}/OutgoingInvoice?page={page}&pageSize=1000', headers=hdrs, timeout=60)
    if not r.ok:
        print(f'Faktura-feil: {r.status_code} {r.text[:200]}')
        break
    data = r.json()
    batch = data.get('data', data) if isinstance(data, dict) else data
    if not isinstance(batch, list) or not batch:
        break
    all_invoices.extend(batch)
    print(f'Side {page}: {len(batch)} fakturaer')
    if len(batch) < 1000:
        break
    page += 1

# 5. Hent kundefordringer
ledger_entries = []
r = requests.get(f'{PO_BASE}/CustomerLedger?pageSize=1000', headers=hdrs, timeout=60)
if r.ok:
    ledger_entries = r.json().get('data', [])
    print(f'Posteringer: {len(ledger_entries)}')

# 6. Lagre
output = {
    'generert': datetime.utcnow().isoformat() + 'Z',
    'fakturaer': all_invoices,
    'kunder': customers,
    'kundefordringer': ledger_entries
}
with open('poweroffice-data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, default=str, indent=2)
print(f'Ferdig! {len(all_invoices)} fakturaer, {len(customers)} kunder')
