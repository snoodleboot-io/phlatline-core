# Installation

## Requirements

- Python **3.11, 3.12, or 3.13**
- pip ≥ 23 (ships with Python 3.11+)

## Standard install

```bash
pip install phlatline-core
phlatline --version
```

For a project-local install:

```bash
python -m venv .venv && source .venv/bin/activate
pip install phlatline-core
phlatline --version
```

## Optional: the fuzzing stage

The fuzz stage is powered by [Schemathesis](https://schemathesis.readthedocs.io/), which is
**not** installed by default — it pulls in Hypothesis and a larger dependency tree than most
users need. Without it, `phlatline scan` still runs the happy-path, boundary, and auth-missing
stages and reports the fuzz stage as skipped.

```bash
pip install 'phlatline-core[fuzz]'
```

Use `--no-fuzz` to skip the stage explicitly even when it is installed.

## Troubleshooting

For a full troubleshooting guide including network errors, auth failures, and Docker usage,
see [INSTALL.md](https://github.com/snoodleboot-io/phlatline-core/blob/main/INSTALL.md) in the repository.

### Quick reference

| Problem | Fix |
|---|---|
| `SchemaLoadError: httpx.ConnectError` | Check network; try `--no-verify-ssl` for internal APIs |
| `SchemaLoadError: URL returned non-schema content` | The spec path is wrong; try `/openapi.json`, `/swagger.json`, or `/docs/openapi.json` |
| `AuthError: unsupported auth type "apikey"` | Use `api_key` (with underscore) in `auth.yaml` |
| `ERROR: Requires-Python >=3.11` | Upgrade Python: `pyenv install 3.11` |
| Every test returns 401 | Check the token in your `auth.yaml` config |

### Docker (no local Python install needed)

```bash
docker run --rm -v "$(pwd):/work" -w /work python:3.11-slim \
    sh -c "pip install phlatline-core && phlatline scan openapi.yaml"
```
