"""
Vexter Dashboard – PowerOffice datafetcher (debug)
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

# 2. Test ulike URL-varianter med full respons
urls = [
    'https://goapi.poweroffice.net/v2/Customer',
    'https://goapi.poweroffice.net/v2/customer',
    'https://goapi.poweroffice.net/Customer',
    'https://goapi.poweroffice.net/customer',
    'https://goapi.poweroffice.net/v2/OutgoingInvoice',
    'https://goapi.poweroffice.net/v2/outgoinginvoice',
]

for url in urls:
    r = requests.get(url + '?pageSize=1', headers=hdrs, timeout=15)
    print(f'{r.status_code} | {url} | {r.text[:150]}')
