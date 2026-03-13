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
token_resp.raise_for_status()
access_token = token_resp.json()["access_token"]
print("  Token hentet OK")

AUTH_HEADERS = {
    "Authorization": f"Bearer {access_token}",
    "Ocp-Apim-Subscription-Key": SUB_KEY,
    "Accept": "application/json",
}

def get_paged(endpoint, extra_params=None):
    """Henter alle sider med PageNumber/PageSize-paginering."""
    results = []
    page = 1
    while True:
        params = {"PageNumber": page, "PageSize": 100}
        if extra_params:
            params.update(extra_params)
        r = requests.get(f"{API_URL}/{endpoint}", headers=AUTH_HEADERS, params=params)
        print(f"  GET {endpoint} side {page}: {r.status_code}")
        if not r.ok:
            print(f"  Feil: {r.text[:400]}")
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
        print(f"    → {len(items)} poster på denne siden (totalt: {len(results)})")
        if len(items) < 100:
            break
        page += 1
    return results

# --- 2. Hent kunder ---
print("\nHenter kunder...")
customers = get_paged("customers")
print(f"  → Totalt {len(customers)} kunder hentet")

# --- 3. Hent utgående fakturaer ---
# Prøv med datofilter; API-et ignorerer ukjente parametrar, så det er trygt
print("\nHenter fakturaer...")
from_date = (datetime.now() - timedelta(days=548)).strftime("%Y-%m-%d")
invoices = get_paged("outgoinginvoices", {"createdDateFrom": from_date})
print(f"  → Totalt {len(invoices)} fakturaer hentet")

# Skriv ut første faktura for å se feltnavnene
if invoices:
    print("\nEksempel faktura-felt:")
    print(json.dumps(list(invoices[0].keys()), indent=2))

if customers:
    print("\nEksempel kunde-felt:")
    print(json.dumps(list(customers[0].keys()), indent=2))

# --- 4. Lagre som JSON ---
output = {
    "hentetTidspunkt": datetime.now().isoformat(),
    "miljo": "demo",
    "fakturaer": invoices,
    "kunder": customers,
}

with open("poweroffice-data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("\nFerdig! Data lagret i poweroffice-data.json")
