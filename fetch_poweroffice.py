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

PO_AUTH    = 'https://goapi.poweroffice.net/OAuth/Token'   # V2 auth
PO_BASE    = 'https://goapi.poweroffice.net/v2'            # V2 base
PO_AUTH_V1 = 'https://api.poweroffice.net/OAuth/Token'     # V1 auth
PO_BASE_V1 = 'https://api.poweroffice.net/api'             # V1 base

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

# 2. Hent V1 token (separat fra V2)
print('\nHenter V1 tilgangstoken...')
token_v1 = None
hdrs_v1 = None
try:
    v1_resp = requests.post(
        PO_AUTH_V1,
        auth=(APP_KEY, CLIENT_KEY),
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data={'grant_type': 'client_credentials'},
        timeout=30
    )
    if v1_resp.ok:
        token_v1 = v1_resp.json().get('access_token')
        hdrs_v1 = {'Authorization': f'Bearer {token_v1}'}
        print('V1 Token OK')
    else:
        print(f'V1 Token feil {v1_resp.status_code}: {v1_resp.text[:200]}')
except Exception as e:
    print(f'V1 Token unntak: {e}')

def safe_get_v1(endpoint):
    """Henter data fra V1 endepunkt."""
    if not hdrs_v1:
        return []
    url = f'{PO_BASE_V1}/{endpoint}'
    try:
        r = requests.get(url, headers=hdrs_v1, timeout=60)
        if r.ok:
            d = r.json()
            # V1 returnerer data direkte eller i 'data'/'Data'
            result = d.get('data', d.get('Data', d)) if isinstance(d, dict) else d
            if isinstance(result, list):
                print(f'  ✓ V1 /{endpoint}: {len(result)} poster')
                return result
            else:
                print(f'  V1 /{endpoint}: ukjent format: {str(result)[:100]}')
                return []
        elif r.status_code == 404:
            print(f'  V1 /{endpoint}: ikke funnet (404)')
            return []
        elif r.status_code == 403:
            print(f'  V1 /{endpoint}: ingen tilgang (403)')
            return []
        else:
            print(f'  V1 /{endpoint}: feil {r.status_code} – {r.text[:150]}')
            return []
    except Exception as e:
        print(f'  V1 /{endpoint}: unntak – {e}')
        return []

# 3. Sjekk tilgangsrettigheter
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
if customers:
    first_c = customers[0]
    print(f'  DEBUG første kunde – alle felter:')
    for k, v in first_c.items():
        print(f'    {k}: {repr(v)[:80]}')

# Bygg oppslagstabell: kunde-ID → navn
customer_id_to_name = {}
for c in customers:
    cid = c.get('Id') or c.get('id') or c.get('CustomerNo') or c.get('Code')
    cname = (c.get('Name') or c.get('DisplayName') or c.get('FullName')
             or c.get('CustomerName') or c.get('ContactName') or str(cid))
    if cid is not None:
        customer_id_to_name[str(cid)] = str(cname).strip()
print(f'  Oppslagstabell: {len(customer_id_to_name)} kunder med ID→navn')

# 3. Utgående fakturaer (inntekter)
print('\nHenter utgående fakturaer...')
outgoing_invoices = safe_get('OutgoingInvoices')

# 4. Gjentagende/repeterende fakturaer
#    Prøver V2 SalesOrders og V1 RecurringInvoice
print('\nHenter gjentagende/repeterende fakturaer...')
recurring_orders = safe_get('SalesOrders') or safe_get('SalesOrder')
# V1 forsøk hvis V2 gir lite
v1_recurring = safe_get_v1('recurringinvoice') or safe_get_v1('RecurringInvoice') or safe_get_v1('recurring-invoice')
if v1_recurring:
    print(f'  -> Bruker V1 gjentagende fakturaer ({len(v1_recurring)} stk)')
    recurring_orders = v1_recurring

# 5. Innkommende fakturaer (kostnader)
#    V2 Reporting/ + V1 fallback
print('\nHenter innkommende fakturaer (kostnader)...')
incoming_invoices = (
    safe_get('Reporting/IncomingInvoices')
    or safe_get_v1('invoice/incoming')
    or safe_get_v1('IncomingInvoice')
    or safe_get_v1('supplierinvoice')
    or safe_get_v1('SupplierInvoice')
)

# 6. Kontopostinger – full regnskapshistorikk
print('\nHenter kontopostinger (regnskap)...')
account_transactions = (
    safe_get('Reporting/AccountTransactions')
    or safe_get_v1('accounttransaction')
    or safe_get_v1('AccountTransaction')
    or safe_get_v1('journalentry')
    or safe_get_v1('voucher')
)

# 7. Kundekonto
print('\nHenter kundekonto...')
customer_ledger = (
    safe_get('Reporting/CustomerLedger')
    or safe_get_v1('customerledger')
    or safe_get_v1('CustomerLedger')
)

# 8. Leverandørkonto
print('\nHenter leverandørkonto...')
supplier_ledger = (
    safe_get('Reporting/SupplierLedger')
    or safe_get_v1('supplierledger')
    or safe_get_v1('SupplierLedger')
)

# 9. Produkter
print('\nHenter produkter...')
products = safe_get('Products')

# 10. Utled MRR per kunde fra fakturahistorikk
# Siden /Reporting/RecurringInvoice ikke er tilgjengelig, bruker vi fakturamønster:
# - Finner siste faktura per kunde (ekskluderer engangskjøp)
# - Bestemmer frekvens (månedlig/kvartalsvis/årlig) fra fakturahistorikk
# - Normaliserer til månedlig MRR
print('\nUtleder MRR fra fakturahistorikk...')

# Debug: vis struktur på første faktura for å finne riktige feltnavn
if outgoing_invoices:
    first = outgoing_invoices[0]
    print(f'  DEBUG første faktura – alle felter:')
    for k, v in first.items():
        print(f'    {k}: {repr(v)[:80]}')
    print(f'  (totalt {len(first)} felter)')

ONE_TIME_KEYWORDS = ['resultatgaranti', 'oppstart', 'onboarding', 'kampanje', 'etablering']

def get_invoice_date(inv):
    for field in ['InvoiceDate', 'OrderDate', 'OutgoingInvoiceDate', 'CreatedDateTimeOffset',
                  'SentDate', 'Date', 'date', 'invoiceDate', 'DueDate']:
        val = inv.get(field)
        if val and str(val) not in ('None', 'null', ''):
            try:
                return datetime.fromisoformat(str(val)[:19].replace('T', ' '))
            except Exception:
                pass
    return None

def get_customer_name(inv):
    # Prøv direkte navnefelt først
    for field in ['CustomerName', 'ContactName', 'DebtorName', 'DebtorCustomerName',
                  'ContactPersonName', 'Name', 'name']:
        val = inv.get(field)
        if val and str(val).strip() and str(val).strip() not in ('None', '0', 'null'):
            return str(val).strip()
    # Slå opp via ID fra oppslagstabellen
    for id_field in ['ContactId', 'CustomerId', 'DebtorId', 'ContactCode',
                     'CustomerNo', 'DebtorNo']:
        cid = inv.get(id_field)
        if cid is not None:
            name = customer_id_to_name.get(str(cid))
            if name and name not in ('None', '0', 'null'):
                return name
    return None

def is_one_time(inv):
    desc = ' '.join([
        str(inv.get('Description', '')),
        str(inv.get('ProductName', '')),
        str(inv.get('Lines', '')),
    ]).lower()
    return any(kw in desc for kw in ONE_TIME_KEYWORDS)

def get_amount(inv):
    for field in ['NetAmount', 'GrossAmount', 'TotalIncludingVat', 'TotalExcludingVat',
                  'Amount', 'TotalAmount', 'RestAmount', 'amount', 'total']:
        val = inv.get(field)
        if val is not None:
            try:
                f = float(val)
                if f != 0.0:
                    return f
            except Exception:
                pass
    return 0.0

# Grupper fakturaer per kunde (ekskluder engangskjøp)
from collections import defaultdict
cust_invoices = defaultdict(list)
no_name = 0
no_date = 0
no_amt = 0
for inv in outgoing_invoices:
    name = get_customer_name(inv)
    if not name:
        no_name += 1
        continue
    if is_one_time(inv):
        continue
    d = get_invoice_date(inv)
    if not d:
        no_date += 1
        continue
    amt = get_amount(inv)
    if not amt or amt <= 0:
        no_amt += 1
        continue
    # Ekskluder kreditnotaer
    vtype = str(inv.get('VoucherType', '')).lower()
    if 'credit' in vtype or 'kreditnota' in vtype:
        continue
    cust_invoices[name].append((d, amt))
print(f'  DEBUG: {len(cust_invoices)} kunder funnet, {no_name} uten navn, {no_date} uten dato, {no_amt} uten beløp')

# Bestem MRR per kunde
now = datetime.utcnow()
mrr_per_kunde = {}
mrr_detaljer = {}

for name, invoices in cust_invoices.items():
    invoices.sort(key=lambda x: x[0])
    last_date, last_amt = invoices[-1]

    # Sjekk om kunden fortsatt er aktiv (siste faktura innen 400 dager)
    days_since = (now - last_date).days
    if days_since > 400:
        continue  # Sannsynlig churn

    # Bestem fakturafrekvens fra mellomrom mellom siste fakturaer
    if len(invoices) >= 2:
        gaps = []
        for i in range(max(0, len(invoices)-4), len(invoices)-1):
            gap = (invoices[i+1][0] - invoices[i][0]).days
            if gap > 10:  # ignorer duplikater
                gaps.append(gap)
        avg_gap = sum(gaps) / len(gaps) if gaps else 30
    else:
        avg_gap = 30  # default månedlig

    # Normaliser til MRR
    if avg_gap < 45:       # Månedlig
        mrr = last_amt
        freq = 'monthly'
    elif avg_gap < 110:    # Kvartalsvis
        mrr = last_amt / 3
        freq = 'quarterly'
    elif avg_gap < 200:    # Halvårlig
        mrr = last_amt / 6
        freq = 'semiannual'
    else:                  # Årlig
        mrr = last_amt / 12
        freq = 'annual'

    mrr_per_kunde[name] = round(mrr)
    mrr_detaljer[name] = {
        'mrr': round(mrr),
        'frekvens': freq,
        'sisteBeloep': round(last_amt),
        'sisteFaktura': last_date.strftime('%Y-%m-%d'),
        'antallFakturaer': len(invoices),
    }

total_mrr = sum(mrr_per_kunde.values())
print(f'  ✓ MRR utledet for {len(mrr_per_kunde)} kunder, total MRR = kr {total_mrr:,.0f}')

# Vis topp 10 for debugging
sorted_mrr = sorted(mrr_detaljer.items(), key=lambda x: -x[1]['mrr'])
for name, d in sorted_mrr[:10]:
    print(f'    {name}: kr {d["mrr"]} ({d["frekvens"]}, siste {d["sisteFaktura"]})')

# 11. Lagre JSON
print('\n=== Lagrer poweroffice-data.json ===')
output = {
    'generert': datetime.utcnow().isoformat() + 'Z',
    'kunder': customers,
    'fakturaer': outgoing_invoices,
    'mrrPerKunde': mrr_per_kunde,       # MRR utledet fra fakturamønster
    'mrrDetaljer': mrr_detaljer,        # Detaljert MRR-info per kunde
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
print(f'  MRR utledet kunder:    {len(mrr_per_kunde)} (kr {sum(mrr_per_kunde.values()):,.0f}/mnd)')
print(f'  Gjentagende ordrer:    {len(recurring_orders)}')
print(f'  Innkommende fakturaer: {len(incoming_invoices)}')
print(f'  Kontopostinger:        {len(account_transactions)}')
print(f'  Kundekonto:            {len(customer_ledger)}')
print(f'  Leverandørkonto:       {len(supplier_ledger)}')
print(f'  Produkter:             {len(products)}')
