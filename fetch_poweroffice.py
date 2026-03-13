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

# --- 2. Diagnose: prøv ulike parameterkombinasjonar for kjente endepunkter ---
print("\n=== DIAGNOSTIKK – parametrar for 'customers' ===")
param_variants = [
    {},
    {"$top": 1},
    {"$skip": 0, "$top": 1},
    {"page": 1, "pageSize": 1},
    {"page": 0, "pageSize": 1},
    {"PageIndex": 0, "PageSize": 1},
    {"PageNumber": 1, "PageSize": 1},
    {"offset": 0, "limit": 1},
]
for pv in param_variants:
    r = requests.get(f"{API_URL}/customers", headers=AUTH_HEADERS, params=pv)
    print(f"  {r.status_code}  params={pv}")
    if r.ok or r.status_code not in (400, 404):
        print(f"  Svar: {r.text[:300]}")
    elif r.status_code == 400:
        print(f"  400-melding: {r.text[:300]}")

print("\n=== DIAGNOSTIKK – parametrar for 'outgoinginvoices' ===")
for pv in param_variants:
    r = requests.get(f"{API_URL}/outgoinginvoices", headers=AUTH_HEADERS, params=pv)
    print(f"  {r.status_code}  params={pv}")
    if r.ok:
        print(f"  Svar: {r.text[:300]}")
    elif r.status_code == 400:
        print(f"  400-melding: {r.text[:300]}")
