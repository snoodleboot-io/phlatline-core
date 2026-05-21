# Quickstart

Phlatline is an OpenAPI-driven API diagnostic CLI. Point it at a spec and get a
report of boundary failures, fuzz hits, and schema drift — in minutes, not hours.

## Install

```bash
pip install phlatline-core
```

Requires Python **3.11, 3.12, or 3.13**.

## Your first diagnostic

```bash
phlatline scan https://petstore3.swagger.io/api/v3/openapi.json
```

Phlatline will:

1. Load the OpenAPI spec from the URL (or a local file)
2. Generate test cases across four categories — happy path, boundary, fuzz, and auth missing
3. Execute each case against the live API
4. Write an HTML report to `./phlatline_results/`

Open `./phlatline_results/phlatline-run/report.html` in a browser to review the results.

## With a local spec

```bash
phlatline scan my-api.yaml
phlatline scan ./openapi.json --output-dir ./reports
```

## With authentication

Create `auth.yaml`:

```yaml
type: bearer
token: "your-token-here"
```

Then pass it:

```bash
phlatline scan my-api.yaml --config auth.yaml
```

Supported auth types: `bearer`, `basic`, `api_key`, `oauth2`.
See [CLI reference](cli-reference.md) for the full options and [Configuration](config-reference.md) for auth config format.

## Multi-target project

Create `phlatline.yaml`:

```yaml
name: my-project
targets:
  - name: prod
    schema: https://api.example.com/openapi.json
    base_url: https://api.example.com
  - name: staging
    schema: ./openapi.yaml
    base_url: https://staging.example.com
```

Run all targets:

```bash
phlatline project phlatline.yaml
```

Results are written per-target under `./phlatline_results/`.

## What gets tested

| Category | What it does |
|---|---|
| **Happy path** | Verifies 2xx responses for valid, in-spec inputs |
| **Boundary** | Tests numeric min/max, empty strings, `MAX_INT32`, max-length strings |
| **Fuzz** | Hypothesis-driven random valid inputs — surfaces unexpected 500s |
| **Auth missing** | Confirms the API rejects requests with no credentials (401/403) |

## What's next

- [Installation & troubleshooting](install.md) — problems with pip, Docker, auth, Python version
- [CLI reference](cli-reference.md) — every flag explained
- [Configuration](config-reference.md) — `phlatline.yaml` schema
- [CI recipes](ci-recipes.md) — drop-in GitHub Actions, GitLab CI, CircleCI snippets
- [FAQ](faq.md) — common questions
