"""
Vexter Dashboard - PowerOffice datafetcher
Kjores av GitHub Actions og lagrer poweroffice-data.json i repoet.
Henter ALL tilgjengelig data fra PowerOffice Go API v2.
"""
import requests
import json
import os
import sys
import statistics
from datetime import datetime
from collections import defaultdict

APP_KEY    = os.environ.get('PO_APP_KEY', '')
CLIENT_KEY = os.environ.get('PO_CLIENT_KEY', '')
SUB_KEY    = os.environ.get('PO_SUB_KEY', '')

PO_AUTH    = 'https://goapi.poweroffice.net/OAuth/Token'   # V2 auth
PO_BASE    = 'https://goapi.poweroffice.net/v2'            # V2 base
PO_AUTH_V1 = 'https://api.poweroffice.net/OAuth/Token'     # V1 auth
PO_BASE_V1 = 'https://api.poweroffice.net/api'             # V1 base

if not all([APP_KEY, CLIENT_KEY, SUB_KEY]):
    print('FEIL: Mangler en eller flere nokler (PO_APP_KEY, PO_CLIENT_KEY, PO_SUB_KEY)')
    sys.exit(1)

# 1. Hent OAuth-token V2
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
    """Henter data fra V2 endepunkt. Returnerer liste."""
    url = f'{PO_BASE}/{endpoint}'
    try:
        r = requests.get(url, headers=hdrs, timeout=60)
        if r.ok:
            d = r.json()
            result = d.get('data', d) if isinstance(d, dict) else d
            if isinstance(result, list):
                print(f'  OK /{endpoint}: {len(result)} poster')
                return result
            else:
                print(f'  /{endpoint}: ukjent format: {str(result)[:100]}')
                return []
        elif r.status_code == 404:
            print(f'  /{endpoint}: ikke funnet (404)')
            return []
        elif r.status_code == 403:
            print(f'  /{endpoint}: ingen tilgang (403)')
            return []
        else:
            print(f'  /{endpoint}: feil {r.status_code} - {r.text[:150]}')
            return []
    except Exception as e:
        print(f'  /{endpoint}: unntak - {e}')
        return []

# 2. Hent V1 token
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
            result = d.get('data', d.get('Data', d)) if isinstance(d, dict) else d
            if isinstance(result, list):
                print(f'  OK V1 /{endpoint}: {len(result)} poster')
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
            print(f'  V1 /{endpoint}: feil {r.status_code} - {r.text[:150]}')
            return []
    except Exception as e:
        print(f'  V1 /{endpoint}: unntak - {e}')
        return []

# 3. Sjekk tilgangsrettigheter
print('\nSjekker tilgangsrettigheter...')
try:
    ci_resp = requests.get(f'{PO_BASE}/ClientIntegrationInformation', headers=hdrs, timeout=30)
    if ci_resp.ok:
        ci = ci_resp.json()
        print(f'  Klientnavn: {ci.get("ClientName", "?")}')
        print(f'  ValidPrivileges: {ci.get("ValidPrivileges", [])}')
    else:
        print(f'  ClientIntegrationInformation: {ci_resp.status_code}')
except Exception as e:
    print(f'  Feil: {e}')

# 4. Kunder
print('\nHenter kunder...')
customers = safe_get('Customers')

# Bygg oppslagstabell: kunde-ID → navn (bekreftet felt: Id, Name)
customer_id_to_name = {}
for c in customers:
    cid = c.get('Id') or c.get('id') or c.get('CustomerNo') or c.get('Code')
    cname = (c.get('Name') or c.get('DisplayName') or c.get('FullName')
             or c.get('CustomerName') or c.get('ContactName') or str(cid))
    if cid is not None:
        customer_id_to_name[str(cid)] = str(cname).strip()
print(f'  Oppslagstabell: {len(customer_id_to_name)} kunder med ID->navn')

# 5. Utgaende fakturaer (inntekter)
print('\nHenter utgaende fakturaer...')
outgoing_invoices = safe_get('OutgoingInvoices')

# 6. Gjentagende/repeterende fakturaer
print('\nHenter gjentagende/repeterende fakturaer...')
recurring_orders = safe_get('SalesOrders') or safe_get('SalesOrder')
v1_recurring = (safe_get_v1('recurringinvoice')
                or safe_get_v1('RecurringInvoice')
                or safe_get_v1('recurring-invoice'))
if v1_recurring:
    print(f'  -> Bruker V1 gjentagende fakturaer ({len(v1_recurring)} stk)')
    recurring_orders = v1_recurring

# 7. Innkommende fakturaer (kostnader)
print('\nHenter innkommende fakturaer (kostnader)...')
incoming_invoices = (
    safe_get('Reporting/IncomingInvoices')
    or safe_get_v1('invoice/incoming')
    or safe_get_v1('IncomingInvoice')
    or safe_get_v1('supplierinvoice')
    or safe_get_v1('SupplierInvoice')
    or []
)

# 8. Kontopostinger (ValidPrivileges: AccountTransaction)
print('\nHenter kontopostinger...')
account_transactions = (
    safe_get('AccountTransactions')
    or safe_get('AccountTransaction')
    or safe_get('Reporting/AccountTransactions')
    or safe_get_v1('accounttransaction')
    or safe_get_v1('AccountTransaction')
    or []
)

# 9. Kundekonto (ValidPrivileges: CustomerLedger)
print('\nHenter kundekonto...')
customer_ledger = (
    safe_get('CustomerLedger')
    or safe_get('Reporting/CustomerLedger')
    or safe_get_v1('customerledger')
    or safe_get_v1('CustomerLedger')
    or []
)

# 10. Bilag (ValidPrivileges: BankVoucher, CashVoucher)
print('\nHenter bilag...')
bank_vouchers = safe_get('BankVouchers') or safe_get('BankVoucher') or []
cash_vouchers = safe_get('CashVouchers') or safe_get('CashVoucher') or []

# 11. Leverandorkonto
print('\nHenter leverandorkonto...')
supplier_ledger = (
    safe_get('SupplierLedger')
    or safe_get('Reporting/SupplierLedger')
    or safe_get_v1('supplierledger')
    or safe_get_v1('SupplierLedger')
    or []
)

# 12. Produkter
print('\nHenter produkter...')
products = safe_get('Products')

# 13. Utled MRR per kunde fra fakturahistorikk
# Feltnavnene er bekreftet: CustomerId -> oppslagstabell -> Name, OrderDate, NetAmount
print('\nUtleder MRR fra fakturahistorikk...')

ONE_TIME_KEYWORDS = ['resultatgaranti', 'oppstart', 'onboarding', 'kampanje', 'etablering']

def get_invoice_date(inv):
    for field in ['InvoiceDate', 'OrderDate', 'OutgoingInvoiceDate',
                  'CreatedDateTimeOffset', 'SentDate', 'DueDate']:
        val = inv.get(field)
        if val and str(val) not in ('None', 'null', ''):
            try:
                return datetime.fromisoformat(str(val)[:19].replace('T', ' '))
            except Exception:
                pass
    return None

def get_customer_name(inv):
    # Sjekk direkte navnefelt
    for field in ['CustomerName', 'ContactName', 'DebtorName',
                  'DebtorCustomerName', 'ContactPersonName']:
        val = inv.get(field)
        if val and str(val).strip() and str(val).strip() not in ('None', '0', 'null'):
            return str(val).strip()
    # Slaa opp via ID (bekreftet felt: CustomerId)
    for id_field in ['CustomerId', 'ContactId', 'DebtorId', 'CustomerNo', 'DebtorNo']:
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
    # Bekreftet felt: NetAmount (positiv = faktura, negativ = kreditnota)
    for field in ['NetAmount', 'TotalAmount', 'GrossAmount',
                  'TotalIncludingVat', 'TotalExcludingVat', 'Amount']:
        val = inv.get(field)
        if val is not None:
            try:
                f = float(val)
                if f != 0.0:
                    return f
            except Exception:
                pass
    return 0.0

# Grupper fakturaer per kunde
cust_invoices = defaultdict(list)
no_name = 0
no_date = 0
no_amt  = 0
for inv in outgoing_invoices:
    name = get_customer_name(inv)
    if not name:
        no_name += 1
        continue
    if is_one_time(inv):
        continue
    # Ekskluder kreditnotaer (negativ NetAmount eller VoucherType)
    vtype = str(inv.get('VoucherType', '')).lower()
    if 'credit' in vtype or 'kreditnota' in vtype:
        continue
    d = get_invoice_date(inv)
    if not d:
        no_date += 1
        continue
    amt = get_amount(inv)
    if amt <= 0:
        no_amt += 1
        continue
    cust_invoices[name].append((d, amt))

print(f'  {len(cust_invoices)} kunder med fakturaer ({no_name} uten navn, {no_date} uten dato, {no_amt} kreditnoter/null)')

# Beregn MRR per kunde
now = datetime.utcnow()
mrr_per_kunde = {}
mrr_detaljer  = {}
skipped_churn = 0

for name, invoices in cust_invoices.items():
    invoices.sort(key=lambda x: x[0])
    last_date, last_amt = invoices[-1]
    days_since = (now - last_date).days

    if len(invoices) == 1:
        # Ny kunde med 1 faktura: teller som manedlig MRR
        # Hopp over kun hvis veldig gammelt (>400 dager = sannsynlig churn)
        if days_since > 400:
            skipped_churn += 1
            continue
        freq = 'monthly'
        mrr  = last_amt
    else:
        # Bestem frekvens fra mellomrom mellom siste 4 fakturaer
        gaps = []
        for i in range(max(0, len(invoices)-4), len(invoices)-1):
            gap = (invoices[i+1][0] - invoices[i][0]).days
            if gap > 10:  # ignorer duplikater/korreksjoner
                gaps.append(gap)
        avg_gap = sum(gaps) / len(gaps) if gaps else 30

        # Frekvensbasert aktivitetstesting
        if avg_gap < 45:        # Manedlig  -> max 65 dager siden siste
            if days_since > 65:
                skipped_churn += 1
                continue
            freq = 'monthly'
        elif avg_gap < 110:     # Kvartalsvis -> max 115 dager
            if days_since > 115:
                skipped_churn += 1
                continue
            freq = 'quarterly'
        elif avg_gap < 200:     # Halvaarlig -> max 210 dager
            if days_since > 210:
                skipped_churn += 1
                continue
            freq = 'semiannual'
        else:                   # Aarlig -> max 380 dager
            if days_since > 380:
                skipped_churn += 1
                continue
            freq = 'annual'

        # Bruk median av siste 3 fakturabelop
        recent_amts = [a for _, a in invoices[-3:]]
        median_amt  = statistics.median(recent_amts)

        if freq == 'monthly':
            mrr = median_amt
        elif freq == 'quarterly':
            mrr = median_amt / 3
        elif freq == 'semiannual':
            mrr = median_amt / 6
        else:
            mrr = median_amt / 12

    mrr_per_kunde[name] = round(mrr)
    mrr_detaljer[name]  = {
        'mrr':             round(mrr),
        'frekvens':        freq,
        'sisteBeloep':     round(last_amt),
        'sisteFaktura':    last_date.strftime('%Y-%m-%d'),
        'antallFakturaer': len(invoices),
        'dagsSiden':       days_since,
    }

total_mrr = sum(mrr_per_kunde.values())
print(f'  OK MRR utledet for {len(mrr_per_kunde)} kunder, total MRR = kr {total_mrr:,.0f}')
print(f'  Hoppet over som churnet: {skipped_churn} kunder')

sorted_mrr = sorted(mrr_detaljer.items(), key=lambda x: -x[1]['mrr'])
for nm, d in sorted_mrr:
    print(f'    {nm}: kr {d["mrr"]} ({d["frekvens"]}, {d["antallFakturaer"]} fakt, {d["dagsSiden"]}d siden)')

# 14. Lagre JSON
print('\n=== Lagrer poweroffice-data.json ===')
output = {
    'generert':            datetime.utcnow().isoformat() + 'Z',
    'kunder':              customers,
    'fakturaer':           outgoing_invoices,
    'mrrPerKunde':         mrr_per_kunde,
    'mrrDetaljer':         mrr_detaljer,
    'gjentagendeOrdre':    recurring_orders,
    'innkommendeFakturaer': incoming_invoices,
    'kontopostinger':      account_transactions,
    'kundekonto':          customer_ledger,
    'leverandorkonto':     supplier_ledger,
    'bankbilag':           bank_vouchers,
    'kassabilag':          cash_vouchers,
    'produkter':           products,
}

with open('poweroffice-data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, default=str, indent=2)

size_kb = os.path.getsize('poweroffice-data.json') / 1024
print(f'\nFerdig! poweroffice-data.json ({size_kb:.1f} KB)')
print(f'  Kunder:                {len(customers)}')
print(f'  Utgaende fakturaer:    {len(outgoing_invoices)}')
print(f'  MRR utledet kunder:    {len(mrr_per_kunde)} (kr {sum(mrr_per_kunde.values()):,.0f}/mnd)')
print(f'  Gjentagende ordrer:    {len(recurring_orders)}')
print(f'  Innkommende fakturaer: {len(incoming_invoices)}')
print(f'  Kontopostinger:        {len(account_transactions)}')
print(f'  Kundekonto:            {len(customer_ledger)}')
print(f'  Bankbilag:             {len(bank_vouchers)}')
print(f'  Kassabilag:            {len(cash_vouchers)}')
print(f'  Leverandorkonto:       {len(supplier_ledger)}')
print(f'  Produkter:             {len(products)}')
