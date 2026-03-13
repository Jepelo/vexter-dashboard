"""
Henter brukeraktivitetsdata fra PostHog API og lagrer som posthog-data.json
"""

import os
import json
import requests
from datetime import datetime

API_KEY    = os.environ["POSTHOG_API_KEY"]
PROJECT_ID = "19751"
BASE_URL   = "https://eu.posthog.com"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

def run_query(hogql):
    """Kjoer en HogQL-sporrring mot PostHog Query API."""
    r = requests.post(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/query/",
        headers=HEADERS,
        json={"query": {"kind": "HogQLQuery", "query": hogql}},
    )
    print(f"  Query status: {r.status_code}")
    if not r.ok:
        print(f"  Feil: {r.text[:400]}")
        r.raise_for_status()
    data = r.json()
    columns = [c["name"] if isinstance(c, dict) else c for c in data.get("columns", [])]
    rows = data.get("results", [])
    return [dict(zip(columns, row)) for row in rows]

# --- 1. Sesjonssammendrag per bruker (siste 18 mnd) ---
print("Henter sesjonssammendrag per bruker...")
user_summary = run_query("""
    SELECT
        person.properties.$email AS email,
        count()                  AS total_sessions,
        round(avg(dateDiff('second', $start_timestamp, $end_timestamp) / 60.0), 1) AS avg_duration_min,
        max($start_timestamp)    AS last_session,
        min($start_timestamp)    AS first_session
    FROM sessions
    WHERE $start_timestamp >= now() - INTERVAL 18 MONTH
      AND person.properties.$email IS NOT NULL
      AND person.properties.$email != ''
    GROUP BY email
    ORDER BY total_sessions DESC
""")
print(f"  -> {len(user_summary)} brukere")

# --- 2. Ukentlig aktivitet per bruker (siste 12 uker) ---
print("Henter ukentlig aktivitet...")
weekly_per_user = run_query("""
    SELECT
        toMonday($start_timestamp)  AS week,
        person.properties.$email    AS email,
        count()                     AS sessions
    FROM sessions
    WHERE $start_timestamp >= now() - INTERVAL 12 WEEK
      AND person.properties.$email IS NOT NULL
      AND person.properties.$email != ''
    GROUP BY week, email
    ORDER BY week, email
""")
print(f"  -> {len(weekly_per_user)} rader")

# --- 3. Manedlig stickiness (DAU/MAU) ---
print("Henter manedlig stickiness...")
monthly_stats = run_query("""
    SELECT
        toStartOfMonth($start_timestamp)    AS month,
        count(DISTINCT person.properties.$email) AS mau,
        count()                             AS total_sessions,
        round(count() * 1.0 / count(DISTINCT person.properties.$email), 2) AS sessions_per_user
    FROM sessions
    WHERE $start_timestamp >= now() - INTERVAL 12 MONTH
      AND person.properties.$email IS NOT NULL
      AND person.properties.$email != ''
    GROUP BY month
    ORDER BY month
""")
print(f"  -> {len(monthly_stats)} maneder")

# --- 4. Ukentlig stickiness (sessions per bruker per uke) ---
print("Henter ukentlig stickiness...")
weekly_stats = run_query("""
    SELECT
        toMonday($start_timestamp)          AS week,
        count(DISTINCT person.properties.$email) AS wau,
        count()                             AS total_sessions,
        round(count() * 1.0 / count(DISTINCT person.properties.$email), 2) AS sessions_per_user
    FROM sessions
    WHERE $start_timestamp >= now() - INTERVAL 12 WEEK
      AND person.properties.$email IS NOT NULL
      AND person.properties.$email != ''
    GROUP BY week
    ORDER BY week
""")
print(f"  -> {len(weekly_stats)} uker")

# --- 5. Lagre ---
output = {
    "hentetTidspunkt": datetime.now().isoformat(),
    "projectId": PROJECT_ID,
    "userSummary": user_summary,
    "weeklyPerUser": weekly_per_user,
    "monthlyStats": monthly_stats,
    "weeklyStats": weekly_stats,
}

with open("posthog-data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("Ferdig! Data lagret i posthog-data.json")
