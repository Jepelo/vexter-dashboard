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

def run_query(label, hogql):
    print(f"  Kjoerer: {label}...")
    r = requests.post(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/query/",
        headers=HEADERS,
        json={"query": {"kind": "HogQLQuery", "query": hogql}},
        timeout=120,
    )
    print(f"    Status: {r.status_code}")
    if not r.ok:
        print(f"    Feil: {r.text[:400]}")
        return []
    data = r.json()
    columns = [c["name"] if isinstance(c, dict) else c for c in data.get("columns", [])]
    rows = data.get("results", [])
    print(f"    -> {len(rows)} rader")
    return [dict(zip(columns, row)) for row in rows]

# --- 0. Diagnostikk: finn riktig e-post-felt ---
print("Diagnostikk: finner riktig e-post-felt...")
diag = run_query("E-post felt diagnostikk", """
    SELECT
        count() AS total_events,
        countIf(person.properties.$email IS NOT NULL AND person.properties.$email != '') AS dollar_email_count,
        countIf(person.properties.email IS NOT NULL AND person.properties.email != '') AS plain_email_count,
        any(person.properties.$email) AS sample_dollar_email,
        any(person.properties.email) AS sample_plain_email
    FROM events
    WHERE timestamp >= now() - INTERVAL 30 DAY
""")
if diag:
    d = diag[0]
    print(f"    Totale events: {d.get('total_events')}")
    print(f"    Med $email: {d.get('dollar_email_count')} (eksempel: {d.get('sample_dollar_email')})")
    print(f"    Med email: {d.get('plain_email_count')} (eksempel: {d.get('sample_plain_email')})")
    dollar_count = int(d.get('dollar_email_count') or 0)
    plain_count = int(d.get('plain_email_count') or 0)
    EMAIL_FIELD = "person.properties.$email" if dollar_count >= plain_count else "person.properties.email"
else:
    EMAIL_FIELD = "person.properties.email"

print(f"  -> Bruker felt: {EMAIL_FIELD}")

# --- 1. Individuelle sesjoner (siste 12 mnd) ---
sessions = run_query("Individuelle sesjoner", f"""
    SELECT
        {EMAIL_FIELD}                       AS email,
        $session_id                         AS session_id,
        toString(min(timestamp))            AS session_start,
        dateDiff('minute', min(timestamp), max(timestamp)) AS duration_min
    FROM events
    WHERE timestamp >= now() - INTERVAL 12 MONTH
      AND {EMAIL_FIELD} IS NOT NULL
      AND {EMAIL_FIELD} != ''
    GROUP BY {EMAIL_FIELD}, $session_id
    ORDER BY session_start DESC
    LIMIT 50000
""")

# --- 2. Sesjonssammendrag per bruker ---
user_summary = run_query("Sesjonssammendrag per bruker", f"""
    SELECT
        {EMAIL_FIELD}                       AS email,
        count(DISTINCT $session_id)         AS total_sessions,
        max(timestamp)                      AS last_session,
        min(timestamp)                      AS first_session
    FROM events
    WHERE timestamp >= now() - INTERVAL 18 MONTH
      AND {EMAIL_FIELD} IS NOT NULL
      AND {EMAIL_FIELD} != ''
    GROUP BY email
    ORDER BY total_sessions DESC
""")

# --- 3. Ukentlig aktivitet per bruker (siste 12 uker) ---
weekly_per_user = run_query("Ukentlig aktivitet per bruker", f"""
    SELECT
        toMonday(timestamp)                 AS week,
        {EMAIL_FIELD}                       AS email,
        count(DISTINCT $session_id)         AS sessions
    FROM events
    WHERE timestamp >= now() - INTERVAL 12 WEEK
      AND {EMAIL_FIELD} IS NOT NULL
      AND {EMAIL_FIELD} != ''
    GROUP BY week, email
    ORDER BY week, email
""")

# --- 4. Manedlig stickiness ---
monthly_stats = run_query("Manedlig stickiness", f"""
    SELECT
        toStartOfMonth(timestamp)                       AS month,
        count(DISTINCT {EMAIL_FIELD})                   AS mau,
        count(DISTINCT $session_id)                     AS total_sessions,
        round(count(DISTINCT $session_id) * 1.0
            / nullIf(count(DISTINCT {EMAIL_FIELD}), 0), 2) AS sessions_per_user
    FROM events
    WHERE timestamp >= now() - INTERVAL 12 MONTH
      AND {EMAIL_FIELD} IS NOT NULL
      AND {EMAIL_FIELD} != ''
    GROUP BY month
    ORDER BY month
""")

# --- 5. Ukentlig stickiness ---
weekly_stats = run_query("Ukentlig stickiness", f"""
    SELECT
        toMonday(timestamp)                             AS week,
        count(DISTINCT {EMAIL_FIELD})                   AS wau,
        count(DISTINCT $session_id)                     AS total_sessions,
        round(count(DISTINCT $session_id) * 1.0
            / nullIf(count(DISTINCT {EMAIL_FIELD}), 0), 2) AS sessions_per_user
    FROM events
    WHERE timestamp >= now() - INTERVAL 12 WEEK
      AND {EMAIL_FIELD} IS NOT NULL
      AND {EMAIL_FIELD} != ''
    GROUP BY week
    ORDER BY week
""")

# --- 6. Lagre ---
output = {
    "hentetTidspunkt": datetime.now().isoformat(),
    "projectId": PROJECT_ID,
    "emailField": EMAIL_FIELD,
    "sessions": sessions,
    "userSummary": user_summary,
    "weeklyPerUser": weekly_per_user,
    "monthlyStats": monthly_stats,
    "weeklyStats": weekly_stats,
}

with open("posthog-data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"Ferdig! {len(sessions)} sesjoner, {len(user_summary)} brukere lagret i posthog-data.json")
