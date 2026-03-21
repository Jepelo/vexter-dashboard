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

# 1. Hent OAuth-token (Basic Auth)
print('Henter tilgangstoken...')
token_resp = requests.post(
    PO_AUTH,
    auth=(APP_KEY, CLIENT_KEY),
    headers={
        'Content-Type': 'application/x-www-form-urlencoded',
        'Ocp-Apim-Subscription-Key': SUB_KEY
    },
    data={'grant_type': 'client_credentials'},
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
cust_resp = requests.get(f'{PO_BASE}/Customers?pageSize=1000', headers=hdrs, timeout=30)
cust_resp.raise_for_status()
cust_data = cust_resp.json()
customers = cust_data.get('data', cust_data) if isinstance(cust_data, dict) else cust_data
if not isinstance(customers, list):
    customers = []
print(f'  -> {len(customers)} kunder')

# 3. Hent utgående fakturaer (ingen paginering – API returnerer alle)
print('Henter fakturaer...')
inv_resp = requests.get(f'{PO_BASE}/OutgoingInvoices', headers=hdrs, timeout=120)
inv_resp.raise_for_status()
inv_data = inv_resp.json()
all_invoices = inv_data.get('data', inv_data) if isinstance(inv_data, dict) else inv_data
if not isinstance(all_invoices, list):
    all_invoices = []
print(f'  -> {len(all_invoices)} fakturaer')

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
        ledger_data = ledger_resp.json()
        ledger_entries = ledger_data.get('data', ledger_data) if isinstance(ledger_data, dict) else ledger_data
        if not isinstance(ledger_entries, list):
            ledger_entries = []
        print(f'  -> {len(ledger_entries)} posteringer')
    else:
        print(f'  CustomerLedger feil {ledger_resp.status_code}: {ledger_resp.text[:200]}')
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
