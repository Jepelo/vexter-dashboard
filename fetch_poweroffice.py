"""
Henter faktura- og kundedata fra PowerOffice Go API v2 (demomiljø)
og lagrer som poweroffice-data.json i repoet.
"""

import os
import json
import base64
import requests
from datetime import datetime, timedelta

# --- Konfigurasjon ---
APP_KEY    = os.environ["PO_APPLICATION_KEY"]
CLIENT_KEY = os.environ["PO_CLIENT_KEY"]
SUB_KEY    = os.environ["PO_SUBSCRIPTION_KEY"]

TOKEN_URL = "https://goapi.poweroffice.net/Demo/OAuth/Token"
API_URL   = "https://goapi.poweroffice.net/Demo/v2"

# --- 1. Hent OAuth2 access token ---
credentials = f"{APP_KEY}:{CLIENT_KEY}"
basic_token = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")

TOKEN_HEADERS = {
    "Authorization": f"Basic {basic_token}",
    "Ocp-Apim-Subscription-Key": SUB_KEY,
    "Content-Type": "application/x-www-form-urlencoded",
}

print("Henter access token...")
token_resp = requests.post(TOKEN_URL, data="grant_type=client_credentials", headers=TOKEN_HEADERS)
print(f"  Token-respons: {token_resp.status_code}")
token_resp.raise_for_status()
access_token = token_resp.json()["access_token"]
print("  Token hentet OK")

AUTH_HEADERS = {
    "Authorization": f"Bearer {access_token}",
    "Ocp-Apim-Subscription-Key": SUB_KEY,
    "Accept": "application/json",
}

# --- 2. Finn riktige endepunktsnavn ---
print("\n=== TESTER ENDEPUNKTER ===")
candidates = [
    "customers",
    "Customer",
    "Customers",
    "outgoinginvoices",
    "OutgoingInvoices",
    "outgoing-invoices",
    "reporting/outgoing-invoices",
    "reporting/outgoinginvoices",
    "invoices",
    "Invoices",
    "SentInvoice",
    "SentInvoices",
    "customerinvoices",
    "CustomerInvoices",
    "vouchers/outgoinginvoicejournals",
    "Vouchers/OutgoingInvoiceJournals",
]

working = []
for ep in candidates:
    r = requests.get(f"{API_URL}/{ep}", headers=AUTH_HEADERS, params={"page": 0, "pageSize": 1})
    status = r.status_code
    print(f"  {status}  {ep}")
    if status == 200:
        working.append(ep)

print(f"\n=== FUNGERENDE ENDEPUNKTER: {working} ===\n")

if not working:
    print("Ingen endepunkter fungerte. Skriver ut token-svar for debugging:")
    debug = token_resp.json()
    print(json.dumps(debug, indent=2))
    raise SystemExit("Fant ingen fungerende endepunkter")

# --- 3. Hent data med første fungerende endepunkter ---
def get_paged(endpoint, params=None):
    results = []
    page = 0
    while True:
        p = {"page": page, "pageSize": 100, **(params or {})}
        r = requests.get(f"{API_URL}/{endpoint}", headers=AUTH_HEADERS, params=p)
        print(f"  GET {endpoint} side {page}: {r.status_code}")
        if not r.ok:
            print(f"  Feil: {r.text[:300]}")
            break
        data = r.json()
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("data", data.get("items", data.get("value", [])))
        else:
            items = []
        if not items:
            break
        results.extend(items)
        if len(items) < 100:
            break
        page += 1
    return results

# Hent kunder
customer_ep = next((e for e in working if "customer" in e.lower()), None)
customers = get_paged(customer_ep) if customer_ep else []
print(f"  → {len(customers)} kunder hentet")

# Hent fakturaer
invoice_ep = next((e for e in working if any(w in e.lower() for w in ["invoice","voucher"])), None)
from_date = (datetime.now() - timedelta(days=548)).strftime("%Y-%m-%d")
invoices = get_paged(invoice_ep, {"invoiceDateFrom": from_date}) if invoice_ep else []
print(f"  → {len(invoices)} fakturaer hentet")

# --- 4. Lagre som JSON ---
output = {
    "hentetTidspunkt": datetime.now().isoformat(),
    "miljo": "demo",
    "fungerendeEndepunkter": working,
    "fakturaer": invoices,
    "kunder": customers,
}

with open("poweroffice-data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("Ferdig! Data lagret i poweroffice-data.json")
