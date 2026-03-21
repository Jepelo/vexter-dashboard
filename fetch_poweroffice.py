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

# Debug: test endepunkter
for ep in ['Customer','Customers','OutgoingInvoice','OutgoingInvoices']:
    t = requests.get(f'{BASE}/{ep}?pageSize=1', headers=hdrs, timeout=15)
    print(f'{t.status_code} /{ep}: {t.text[:120]}')
