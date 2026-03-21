"""
Vexter Dashboard – PowerOffice datafetcher
Kjøres av GitHub Actions og lagrer poweroffice-data.json i repoet.
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
PO_BASE = 'https://goapi.poweroffice.net/v2'

if not all([APP_KEY, CLIENT_KEY, SUB_KEY]):
    print('FEIL: Mangler en eller flere nøkler (PO_APP_KEY, PO_CLIENT_KEY, PO_SUB_KEY)')
    sys.exit(1)

# 1. Hent OAuth-token
print('Henter tilgangstoken...')
token_resp = requests.post(
    PO_AUTH,
    headers={
        'Content-Type': 'application/x-www-form-urlencoded',
        'Ocp-Apim-Subscription-Key': SUB_KEY
    },
    data={
        'grant_type': 'client_credentials',
        'client_id': APP_KEY,
        'client_secret': CLIENT_KEY
    },
    timeout=30
)
if not token_resp.ok:
    print(f'Token-feil {token_resp.status_code}: {token_resp.text[:500]}')
    token_resp.raise_for_status()
token = token_resp.json()['access_token']
print('Token OK')

hdrs = {
    'Authorization': f'Bearer {token}',
    'Ocp-Apim-Subscription-Key': SUB_KEY
}

# 2. Hent kunder
print('Henter kunder...')
cust_resp = requests.get(f'{PO_BASE}/Customer?pageSize=1000', headers=hdrs, timeout=30)
cust_resp.raise_for_status()
customers = cust_resp.json().get('data', [])
print(f'  -> {len(customers)} kunder')

# 3. Hent utgaende fakturaer (paginert)
print('Henter fakturaer...')
all_invoices = []
page = 1
while True:
    resp = requests.get(
        f'{PO_BASE}/OutgoingInvoice?page={page}&pageSize=1000',
        headers=hdrs,
        timeout=60
    )
    resp.raise_for_status()
    data = resp.json()
    batch = data.get('data', data) if isinstance(data, dict) else data
    if not isinstance(batch, list) or len(batch) == 0:
        break
    all_invoices.extend(batch)
    print(f'  -> Side {page}: {len(batch)} fakturaer (totalt {len(all_invoices)})')
    if len(batch) < 1000:
        break
    page += 1

# 4. Hent kundefordringer (betalingsstatus)
print('Henter kundefordringer...')
ledger_entries = []
try:
    ledger_resp = requests.get(
        f'{PO_BASE}/CustomerLedger?pageSize=1000',
        headers=hdrs,
        timeout=60
    )
    if ledger_resp.ok:
        ledger_entries = ledger_resp.json().get('data', [])
        print(f'  -> {len(ledger_entries)} posteringer')
except Exception as e:
    print(f'  Kunne ikke hente kundefordringer: {e}')

# 5. Lagre JSON
output = {
    'generert': datetime.utcnow().isoformat() + 'Z',
    'fakturaer': all_invoices,
    'kunder': customers,
    'kundefordringer': ledger_entries
}

with open('poweroffice-data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, default=str, indent=2)

size_kb = os.path.getsize('poweroffice-data.json') / 1024
print(f'\nFerdig! {len(all_invoices)} fakturaer, {len(customers)} kunder, {len(ledger_entries)} posteringer')
print(f'Fil: poweroffice-data.json ({size_kb:.1f} KB)')
