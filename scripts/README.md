# Scripts

Operational scripts used to build and operate AIOfferRadar.

| Script | Purpose |
|--------|---------|
| `youcom_research.py` | Batch web research over the You.com MCP (`balance` / `search` / `contents` modes). Writes raw JSON + a markdown digest to `data/research_raw/`. |
| `youcom_research_batch2.py` | Second research batch (free-tier programs, more platforms). |
| `gen_free_offers.py` | Merges live radar findings with the curated free-service baseline into `docs/free_ai_offers_*.md` + `data/free_ai_offers.html`. |
| `rescore_verdicts.py` | Re-scores stored verification verdicts with the strict evidence rules and rebuilds the verified report. |
| `setup.sh` | (upstream) one-shot VPS setup. |

Run any of them with the project venv:

```bash
.venv\Scripts\python.exe scripts\youcom_research.py balance
.venv\Scripts\python.exe scripts\gen_free_offers.py
```

These read `secrets.env` for `YDC_API_KEY` (the research drivers) or the store at
`data/airadar.db` (the report generators).
