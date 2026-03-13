"""
Henter faktura- og kundedata fra PowerOffice Go API v2 (testmiljø)
og lagrer som poweroffice-data.json i repoet.
"""

import os
import json
import requests
from datetime import datetime, timedelta

# --- Konfigurasjon ---
APP_KEY    = os.environ["PO_APPLICATION_KEY"]
CLIENT_KEY = os.environ["PO_CLIENT_KEY"]
SUB_KEY    = os.environ["PO_SUBSCRIPTION_KEY"]

# Demo/testmiljø – bytt til produksjon når du er klar:
#   Token:  https://goapi.poweroffice.net/OAuth/Token
#   API:    https://goapi.poweroffice.net/v2
TOKEN_URL  = "https://goapi.poweroffice.net/Demo/OAuth/Token"
API_URL    = "https://goapi.poweroffice.net/Demo/v2"

HEADERS_BASE = {
    "Ocp-Apim-Subscription-Key": SUB_KEY,
}

# --- 1. Hent OAuth2 access token ---
print("Henter access token...")
token_resp = requests.post(
    TOKEN_URL,
    data={
        "grant_type": "client_credentials",
        "client_id": APP_KEY,
        "client_secret": CLIENT_KEY,
    },
    headers=HEADERS_BASE,
)
token_resp.raise_for_status()
access_token = token_resp.json()["access_token"]
print("Token hentet OK")

AUTH_HEADERS = {
    **HEADERS_BASE,
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
}

def get_paged(endpoint, params=None):
    """Henter alle sider fra et paginert endepunkt."""
    results = []
    page = 1
    while True:
        p = {"page": page, "pageSize": 100, **(params or {})}
        r = requests.get(f"{API_URL}/{endpoint}", headers=AUTH_HEADERS, params=p)
        r.raise_for_status()
        data = r.json()
        items = data.get("data", data) if isinstance(data, dict) else data
        if not items:
            break
        results.extend(items)
        # Stopp hvis vi fikk færre enn pageSize (siste side)
        if len(items) < 100:
            break
        page += 1
    return results

# --- 2. Hent sendte fakturaer (siste 18 måneder) ---
from_date = (datetime.now() - timedelta(days=548)).strftime("%Y-%m-%d")
print(f"Henter fakturaer fra {from_date}...")
invoices = get_paged("SentInvoice", {"invoiceDateFrom": from_date})
print(f"  → {len(invoices)} fakturaer hentet")

# --- 3. Hent kunder ---
print("Henter kunder...")
customers = get_paged("Customer")
print(f"  → {len(customers)} kunder hentet")

# --- 4. Lagre som JSON ---
output = {
    "hentetTidspunkt": datetime.now().isoformat(),
    "miljo": "demo",
    "fakturaer": invoices,
    "kunder": customers,
}

with open("poweroffice-data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("Ferdig! Data lagret i poweroffice-data.json")
