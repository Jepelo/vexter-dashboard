name: Hent PowerOffice-data

on:
  schedule:
    - cron: '0 4 * * *'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  fetch-data:
    runs-on: ubuntu-latest

    steps:
      - name: Sjekk ut repo
        uses: actions/checkout@v4

      - name: Sett opp Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Installer avhengigheter
        run: pip install requests

      - name: Hent data fra PowerOffice
        env:
          PO_APP_KEY:    ${{ secrets.PO_APP_KEY }}
          PO_CLIENT_KEY: ${{ secrets.PO_CLIENT_KEY }}
          PO_SUB_KEY:    ${{ secrets.PO_SUB_KEY }}
        run: python fetch_poweroffice.py

      - name: Commit og push
        run: |
          git config user.name  "GitHub Actions"
          git config user.email "actions@github.com"
          git add poweroffice-data.json
          git diff --staged --quiet || git commit -m "Oppdater PowerOffice-data $(date +'%Y-%m-%d %H:%M UTC')"
          git push
