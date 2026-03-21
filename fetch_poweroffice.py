"""
Vexter Dashboard – PowerOffice datafetcher
Kjøres av GitHub Actions og lagrer poweroffice-data.json i repoet.
Henter ALL tilgjengelig data fra PowerOffice Go API v2.
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

def safe_get(endpoint, label=None):
    """Henter data fra endepunkt. Returnerer liste, printer status."""
    url = f'{PO_BASE}/{endpoint}'
    lbl = label or endpoint
    try:
        r = requests.get(url, headers=hdrs, timeout=60)
        if r.ok:
            d = r.json()
            result = d.get('data', d) if isinstance(d, dict) else d
            if isinstance(result, list):
                print(f'  ✓ /{endpoint}: {len(result)} poster')
                return result
            else:
                print(f'  /{endpoint}: ukjent format ({type(result).__name__})')
                return []
        elif r.status_code == 404:
            print(f'  /{endpoint}: ikke funnet (404)')
            return []
        elif r.status_code == 403:
            print(f'  /{endpoint}: ingen tilgang (403)')
            return []
        else:
            print(f'  /{endpoint}: feil {r.status_code} – {r.text[:150]}')
            return []
    except Exception as e:
        print(f'  /{endpoint}: unntak – {e}')
        return []

# 2. Kunder
print('\nHenter kunder...')
customers = safe_get('Customers')

# 3. Utgående fakturaer (inntekter)
print('\nHenter utgående fakturaer...')
outgoing_invoices = safe_get('OutgoingInvoices')

# 4. Gjentagende/repeterende ordrer (MRR-kilde)
print('\nHenter gjentagende ordrer...')
recurring_orders = []
for ep in ['RecurringInvoice', 'SalesOrder', 'RecurringOrder', 'SubscriptionOrder']:
    data = safe_get(ep)
    if data:
        recurring_orders = data
        print(f'  -> Bruker /{ep} som kilde for gjentagende ordrer')
        break

# 5. Innkommende fakturaer / leverandørfakturaer (kostnader)
print('\nHenter leverandørfakturaer (kostnader)...')
supplier_invoices = []
for ep in ['SupplierInvoice', 'IncomingInvoice', 'PurchaseInvoice', 'SupplierInvoices']:
    data = safe_get(ep)
    if data:
        supplier_invoices = data
        break

# 6. Kontopostinger / bilag (fullt regnskap)
print('\nHenter kontopostinger...')
account_transactions = []
for ep in ['VoucherTransaction', 'AccountTransaction', 'GeneralLedgerTransaction',
           'Voucher', 'JournalEntry', 'LedgerTransaction']:
    data = safe_get(ep)
    if data:
        account_transactions = data
        break

# 7. Banktransaksjoner
print('\nHenter banktransaksjoner...')
bank_transactions = []
for ep in ['BankStatementEntry', 'BankStatement', 'BankTransaction', 'BankJournal']:
    data = safe_get(ep)
    if data:
        bank_transactions = data
        break

# 8. Produkter
print('\nHenter produkter...')
products = safe_get('Product') or safe_get('Products')

# 9. Kundefordringer (åpne poster)
print('\nHenter åpne poster / kundefordringer...')
open_entries = []
for ep in ['CustomerLedger', 'OutstandingInvoice', 'OpenEntry', 'AccountReceivable']:
    data = safe_get(ep)
    if data:
        open_entries = data
        break

# 10. Lagre JSON
print('\n=== Lagrer poweroffice-data.json ===')
output = {
    'generert': datetime.utcnow().isoformat() + 'Z',
    'kunder': customers,
    'fakturaer': outgoing_invoices,
    'gjentagendeOrdre': recurring_orders,
    'leverandorfakturaer': supplier_invoices,
    'kontopostinger': account_transactions,
    'banktransaksjoner': bank_transactions,
    'produkter': products,
    'apnePostinger': open_entries,
}

with open('poweroffice-data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, default=str, indent=2)

size_kb = os.path.getsize('poweroffice-data.json') / 1024
print(f'\n✓ Ferdig! poweroffice-data.json ({size_kb:.1f} KB)')
print(f'  Kunder:              {len(customers)}')
print(f'  Utgående fakturaer:  {len(outgoing_invoices)}')
print(f'  Gjentagende ordrer:  {len(recurring_orders)}')
print(f'  Leverandørfakturaer: {len(supplier_invoices)}')
print(f'  Kontopostinger:      {len(account_transactions)}')
print(f'  Banktransaksjoner:   {len(bank_transactions)}')
print(f'  Produkter:           {len(products)}')
print(f'  Åpne poster:         {len(open_entries)}')
