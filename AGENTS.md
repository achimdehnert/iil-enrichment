# iil-enrichment — Agent-Kontext

> Schema: pkg-agents-v1 · geprüft von `platform/tools/check_agents_md.py` ·
> GENERIERT von `platform/tools/gen_pkg_agents_md.py` (#2075 K2, ADR-266) —
> nicht von Hand pflegen; Fakten-Drift → Generator erneut laufen lassen.

## Zweck

Enrichment Agent Pattern — bridge managed records with external knowledge sources (ADR-169)

Details und Nutzungsbeispiele: `README.md`. Dieses Paket ist Teil der
iil-PyPI-Fleet (Programm: platform ADR-266 / #2075).

## Setup & Test (Einstiegskommando)

Ein Kommando, frischer Clone, Python >=3.12:

```bash
make setup && make test
```

Keine weiteren Vorbedingungen (kein Postgres, keine Env-Variablen) — wäre das
falsch, ist es ein Schema-Verstoß und gehört hier dokumentiert.

## Public API

Top-Level-Module:

- `enrichment`
- `tests`

Extras: `iil-enrichment[all]`, `iil-enrichment[dev]`, `iil-enrichment[django]`, `iil-enrichment[gestis]`, `iil-enrichment[http]`, `iil-enrichment[pgvector]`, `iil-enrichment[pubchem]`

## Architektur-Constraints

- Library, kein App-Code: keine Deploy-/Prod-Kopplung.
- Änderungen an der Public API sind Semver-relevant (Frühwarn-Metrik #2075 K3).
- CI-Kontrakt: reusable `_ci-pypi.yml` (ADR-226); `make test` muss dem
  CI-Testlauf entsprechen.

## Release

Publish via `publish.yml` (OIDC) — nie manuell (ADR-226/266; Release nur über CI).
