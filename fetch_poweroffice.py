"""
Vexter Dashboard – PowerOffice datafetcher
"""
import requests, json, os, sys
from datetime import datetime

APP_KEY    = os.environ.get('PO_APP_KEY', '')
CLIENT_KEY = os.environ.get('PO_CLIENT_KEY', '')
SUB_KEY    = os.environ.get('PO_SUB_KEY', '')

if not all([APP_KEY, CLIENT_KEY, SUB_KEY]):
    print('FEIL: Mangler nøkler'); sys.exit(1)

print('Henter token...')
r = requests.post('https://goapi.poweroffice.net/OAuth/Token',
    headers={'Content-Type':'application/x-www-form-urlencoded','Ocp-Apim-Subscription-Key':SUB_KEY},
    data={'grant_type':'client_credentials'}, auth=(APP_KEY, CLIENT_KEY), timeout=30)
if not r.ok: print(f'Token-feil: {r.status_code} {r.text[:300]}'); sys.exit(1)
token = r.json()['access_token']
print('Token OK')

hdrs = {'Authorization':f'Bearer {token}','Ocp-Apim-Subscription-Key':SUB_KEY}
BASE = 'https://goapi.poweroffice.net/v2'

# Kunder
r = requests.get(f'{BASE}/Customer?pageSize=1000', headers=hdrs, timeout=30)
customers = r.json().get('data',[]) if r.ok else []
print(f'Kunder: {len(customers)}')

# Fakturaer
all_invoices, page = [], 1
while True:
    r = requests.get(f'{BASE}/OutgoingInvoice?page={page}&pageSize=1000', headers=hdrs, timeout=60)
    if not r.ok: print(f'Faktura-feil {r.status_code}: {r.text[:200]}'); break
    batch = r.json().get('data',[])
    if not batch: break
    all_invoices.extend(batch)
    print(f'Side {page}: {len(batch)} fakturaer')
    if len(batch) < 1000: break
    page += 1

# Kundefordringer
r = requests.get(f'{BASE}/CustomerLedger?pageSize=1000', headers=hdrs, timeout=60)
ledger = r.json().get('data',[]) if r.ok else []
print(f'Posteringer: {len(ledger)}')

json.dump({'generert':datetime.utcnow().isoformat()+'Z','fakturaer':all_invoices,'kunder':customers,'kundefordringer':ledger},
    open('poweroffice-data.json','w',encoding='utf-8'), ensure_ascii=False, default=str, indent=2)
print(f'Ferdig! {len(all_invoices)} fakturaer, {len(customers)} kunder, {len(ledger)} posteringer')
