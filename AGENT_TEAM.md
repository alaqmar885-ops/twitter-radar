# AIOfferRadar Agent Team

AIOfferRadar runs a small **team of single-purpose agents** over a shared blackboard
(`AgentContext`). Each agent has one job, returns a machine-readable `AgentReport`,
and can never crash the run - failures are logged and the pipeline continues.
Every cycle writes `data/runs/run_<ts>.json` with each agent's counts.

| Agent | File | Role | Reads | Writes |
|-------|------|------|-------|--------|
| **ScoutAgent** | `airadar/agents/scout.py` | collect | all enabled platform sources (via `SourceRouter`) | `ctx.items`, `store.items` |
| **TriageAgent** | `airadar/agents/triage.py` | filter | `ctx.items` | `ctx.kept` |
| **AnalystAgent** | `airadar/agents/analyst.py` | classify | `ctx.kept` | `ctx.offers` (clustered, typed, promo codes) |
| **VerifierAgent** | `airadar/agents/verifier.py` | verify | `ctx.offers` | `o.link_ok`, `o.web_verified`, `o.web_sources` |
| **CuratorAgent** | `airadar/agents/curator.py` | rank | `ctx.offers` | merged + scored offers, `store.offers` |
| **ReporterAgent** | `airadar/agents/reporter.py` | render | `ctx.offers` | `data/digests/airadar_digest_*` (html/md/json) |

Orchestrator: `airadar/agents/team.py::AgentTeam.run_once()`.

## Pipeline

```
sources ──> ScoutAgent ──> TriageAgent ──> AnalystAgent ──> VerifierAgent ──> CuratorAgent ──> ReporterAgent
 (HTTP)      items          offer-likes      Offers          link/web proof     scored+stored    digest + run report
```

## Contract

Every agent subclasses `airadar/agents/base.py::Agent`:

```python
class MyAgent(Agent):
    name = "myagent"
    role = "does-one-thing"
    def run(self, ctx: AgentContext) -> AgentReport: ...
```

- `AgentContext` carries `cfg, store, router, classifier, scorer, enricher, offline, items, kept, offers, log`.
- `AgentReport(agent, role, status, counts, notes, elapsed)` -> serialized into the run report.
- `offline=True` runs the whole team on local fixtures with zero network (used by the smoke test).

## Running

```bash
python run_radar.py sources        # sources + availability
python run_radar.py run            # live cycle across platforms
python run_radar.py run --offline  # fixtures only, no network
python run_radar.py report         # re-render from store
python run_radar.py status         # store stats
```

## Adding an agent

1. Create `airadar/agents/<name>.py` subclassing `Agent`.
2. Insert it into the `self.agents` list in `airadar/agents/team.py` at the right stage.
3. If it writes a new field, extend `AgentContext`.
