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

def safe_get(endpoint):
    """Henter data fra endepunkt. Returnerer liste, printer status."""
    url = f'{PO_BASE}/{endpoint}'
    try:
        r = requests.get(url, headers=hdrs, timeout=60)
        if r.ok:
            d = r.json()
            result = d.get('data', d) if isinstance(d, dict) else d
            if isinstance(result, list):
                print(f'  ✓ /{endpoint}: {len(result)} poster')
                return result
            else:
                print(f'  /{endpoint}: ukjent format ({type(result).__name__}): {str(result)[:100]}')
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

# 2. Sjekk tilgangsrettigheter
print('\nSjekker tilgangsrettigheter...')
try:
    ci_resp = requests.get(f'{PO_BASE}/ClientIntegrationInformation', headers=hdrs, timeout=30)
    if ci_resp.ok:
        ci = ci_resp.json()
        print(f'  Klientnavn: {ci.get("ClientName", "?")}')
        privs = ci.get('AccessPrivileges', ci.get('Privileges', ci.get('Subscriptions', [])))
        if privs:
            print(f'  Tilganger: {json.dumps(privs, ensure_ascii=False)[:500]}')
        else:
            print(f'  Full respons: {json.dumps(ci, ensure_ascii=False)[:500]}')
    else:
        print(f'  ClientIntegrationInformation: {ci_resp.status_code}')
except Exception as e:
    print(f'  Feil: {e}')

# 3. Kunder
print('\nHenter kunder...')
customers = safe_get('Customers')

# 3. Utgående fakturaer (inntekter)
print('\nHenter utgående fakturaer...')
outgoing_invoices = safe_get('OutgoingInvoices')

# 4. Gjentagende ordrer – MRR-kilde
#    Riktig sti: SalesOrder (ikke Reporting/)
print('\nHenter gjentagende/repeterende ordrer...')
recurring_orders = safe_get('SalesOrders') or safe_get('SalesOrder')

# 5. Innkommende fakturaer (kostnader) – under Reporting/
print('\nHenter innkommende fakturaer (kostnader)...')
incoming_invoices = safe_get('Reporting/IncomingInvoices')

# 6. Kontopostinger – under Reporting/
print('\nHenter kontopostinger (regnskap)...')
account_transactions = safe_get('Reporting/AccountTransactions')

# 7. Kundekonto – under Reporting/
print('\nHenter kundekonto...')
customer_ledger = safe_get('Reporting/CustomerLedger')

# 8. Leverandørkonto – under Reporting/
print('\nHenter leverandørkonto...')
supplier_ledger = safe_get('Reporting/SupplierLedger')

# 9. Produkter
print('\nHenter produkter...')
products = safe_get('Products')

# 10. Lagre JSON
print('\n=== Lagrer poweroffice-data.json ===')
output = {
    'generert': datetime.utcnow().isoformat() + 'Z',
    'kunder': customers,
    'fakturaer': outgoing_invoices,
    'gjentagendeOrdre': recurring_orders,
    'innkommendeFakturaer': incoming_invoices,
    'kontopostinger': account_transactions,
    'kundekonto': customer_ledger,
    'leverandorkonto': supplier_ledger,
    'produkter': products,
}

with open('poweroffice-data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, default=str, indent=2)

size_kb = os.path.getsize('poweroffice-data.json') / 1024
print(f'\n✓ Ferdig! poweroffice-data.json ({size_kb:.1f} KB)')
print(f'  Kunder:                {len(customers)}')
print(f'  Utgående fakturaer:    {len(outgoing_invoices)}')
print(f'  Gjentagende ordrer:    {len(recurring_orders)}')
print(f'  Innkommende fakturaer: {len(incoming_invoices)}')
print(f'  Kontopostinger:        {len(account_transactions)}')
print(f'  Kundekonto:            {len(customer_ledger)}')
print(f'  Leverandørkonto:       {len(supplier_ledger)}')
print(f'  Produkter:             {len(products)}')
