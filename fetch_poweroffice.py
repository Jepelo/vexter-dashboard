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

# Demomiljø – bytt til produksjon når du er klar:
#   Token:  https://goapi.poweroffice.net/OAuth/Token
#   API:    https://goapi.poweroffice.net/v2
TOKEN_URL = "https://goapi.poweroffice.net/Demo/OAuth/Token"
API_URL   = "https://goapi.poweroffice.net/Demo/v2"

# --- 1. Bygg Basic Auth-header (ApplicationKey:ClientKey, Base64-kodet) ---
credentials = f"{APP_KEY}:{CLIENT_KEY}"
basic_token = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")

TOKEN_HEADERS = {
    "Authorization": f"Basic {basic_token}",
    "Ocp-Apim-Subscription-Key": SUB_KEY,
    "Content-Type": "application/x-www-form-urlencoded",
}

# --- 2. Hent OAuth2 access token ---
print("Henter access token...")
token_resp = requests.post(
    TOKEN_URL,
    data="grant_type=client_credentials",
    headers=TOKEN_HEADERS,
)
print(f"  Token-respons: {token_resp.status_code}")
if not token_resp.ok:
    print(f"  Feil: {token_resp.text}")
token_resp.raise_for_status()
access_token = token_resp.json()["access_token"]
print("  Token hentet OK")

AUTH_HEADERS = {
    "Authorization": f"Bearer {access_token}",
    "Ocp-Apim-Subscription-Key": SUB_KEY,
    "Content-Type": "application/json",
}

def get_paged(endpoint, params=None):
    """Henter alle sider fra et paginert endepunkt (side 0-basert)."""
    results = []
    page = 0
    while True:
        p = {"page": page, "pageSize": 100, **(params or {})}
        url = f"{API_URL}/{endpoint}"
        r = requests.get(url, headers=AUTH_HEADERS, params=p)
        print(f"  GET {endpoint} side {page}: {r.status_code}")
        if not r.ok:
            print(f"  Respons: {r.text[:500]}")
            r.raise_for_status()
        data = r.json()
        # v2 returnerer enten liste direkte, eller {data: [...]}
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("data", data.get("items", []))
        else:
            items = []
        if not items:
            break
        results.extend(items)
        if len(items) < 100:
            break
        page += 1
    return results

# --- 3. Hent utgående fakturaer (siste 18 måneder) ---
from_date = (datetime.now() - timedelta(days=548)).strftime("%Y-%m-%d")
print(f"Henter fakturaer fra {from_date}...")
invoices = get_paged("OutgoingInvoice", {"invoiceDateFrom": from_date})
print(f"  → {len(invoices)} fakturaer hentet")

# --- 4. Hent kunder ---
print("Henter kunder...")
customers = get_paged("Customer")
print(f"  → {len(customers)} kunder hentet")

# --- 5. Lagre som JSON ---
output = {
    "hentetTidspunkt": datetime.now().isoformat(),
    "miljo": "demo",
    "fakturaer": invoices,
    "kunder": customers,
}

with open("poweroffice-data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("Ferdig! Data lagret i poweroffice-data.json")
