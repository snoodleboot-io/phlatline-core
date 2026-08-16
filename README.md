# phlatline-core

**OpenAPI-driven API diagnostic CLI.**  
Point it at a spec, get a report of boundary failures, fuzz hits, and schema drift — in minutes.

[![CI](https://github.com/snoodleboot-io/phlatline-core/actions/workflows/ci.yml/badge.svg)](https://github.com/snoodleboot-io/phlatline-core/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/snoodleboot-io/phlatline-core/branch/main/graph/badge.svg)](https://codecov.io/gh/snoodleboot-io/phlatline-core)
[![PyPI](https://img.shields.io/pypi/v/phlatline-core)](https://pypi.org/project/phlatline-core/)
[![License: BSL 1.1](https://img.shields.io/badge/license-BSL%201.1-blue)](LICENSE)

---

## Quickstart

```bash
pip install 'phlatline-core[fuzz]'
phlatline scan https://petstore3.swagger.io/api/v3/openapi.json
```

That's it. Phlatline loads the spec, generates boundary and fuzz test cases, runs them against the
live API, and writes an HTML report to `./phlatline_results/`.

The `[fuzz]` extra pulls in [Schemathesis](https://schemathesis.readthedocs.io/) for the fuzz
stage. Plain `pip install phlatline-core` works too — every other stage runs, and the fuzz stage
reports itself as skipped.

### With a local spec

```bash
phlatline scan my-api.yaml
phlatline scan ./openapi.json --output-dir ./reports
```

### With authentication

Create `auth.yaml`:

```yaml
type: bearer
token: "your-token-here"
```

Then pass it:

```bash
phlatline scan my-api.yaml --config auth.yaml
```

For more auth options (API key, Basic, OAuth2) see [INSTALL.md](INSTALL.md).

### Multi-target project

Create `phlatline.yaml`:

```yaml
name: my-project
targets:
  - name: prod
    schema: https://api.example.com/openapi.json
    base_url: https://api.example.com
  - name: staging
    schema: https://staging.example.com/openapi.json
    base_url: https://staging.example.com
```

Run all targets:

```bash
phlatline project phlatline.yaml
```

---

## What it checks

| Category | What it does |
|---|---|
| **Happy path** | Verifies 2xx responses for valid inputs |
| **Boundary** | Tests min/max integers, empty strings, max-length strings, `MAX_INT32` |
| **Fuzz** | Random valid inputs via Hypothesis — finds unexpected 500s (needs the `[fuzz]` extra) |
| **Auth missing** | Confirms the API rejects unauthenticated requests (401/403) |

---

## CLI reference

```
phlatline scan SCHEMA [OPTIONS]

  SCHEMA   Path to an OpenAPI/Swagger file, or a URL.

  --base-url TEXT       Override base URL from the schema servers block.
  --config FILE         Path to auth config (JSON or YAML).
  --output-dir TEXT     Where to write reports (default: ./phlatline_results).
  --no-fuzz             Skip the fuzzing stage (faster).
  --fuzz-examples INT   Hypothesis examples per operation (default: 10).
  --no-verify-ssl       Skip TLS certificate verification.
  -h, --help            Show this message and exit.

phlatline project FILE [OPTIONS]

  FILE     Path to a phlatline.yaml multi-target project file.

  --output-dir TEXT     Where to write reports.
  -h, --help            Show this message and exit.
```

---

## Supported formats

- OpenAPI 3.1 (JSON and YAML)
- OpenAPI 3.0 (JSON and YAML)
- Swagger 2.0 (JSON and YAML)
- Local files and HTTPS URLs

---

## Development

```bash
git clone https://github.com/snoodleboot-io/phlatline-core
cd phlatline-core
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pytest
```

Tests use strict ATDD + TDD per [ADR-002](../../docs/decisions/ADR-002-testing-discipline.md).
Coverage target: **85%**.

---

## License

Business Source License 1.1 — free to use for non-production purposes.  
Auto-converts to **Apache 2.0** after 4 years (Change Date: 2029-05-01).

See [LICENSE](LICENSE) and [NOTICE](NOTICE) for the full text and Additional Use Grant.
