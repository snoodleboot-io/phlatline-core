# Installing phlatline-core

## Requirements

- Python **3.11, 3.12, or 3.13**
- pip ≥ 23 (ships with Python 3.11+)
- Network access to your OpenAPI spec (file or URL)

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

---

## Troubleshooting

### Network connection errors

**Symptom** — the CLI fails when loading a spec from a URL:

```
$ phlatline scan https://api.example.com/openapi.json
▸ Loading schema: https://api.example.com/openapi.json
SchemaLoadError: Failed to fetch schema from https://api.example.com/openapi.json:
  httpx.ConnectError: [Errno -3] Temporary failure in name resolution
```

**Causes and fixes:**

1. **No internet / VPN required** — confirm you can `curl https://api.example.com/openapi.json`.
2. **TLS pinning / self-signed cert** — use `--no-verify-ssl` to skip certificate verification:

   ```bash
   $ phlatline scan https://internal-api.corp/openapi.json --no-verify-ssl
   ```

3. **Proxy** — set `HTTPS_PROXY` before running:

   ```bash
   $ HTTPS_PROXY=http://proxy.corp:3128 phlatline scan https://api.example.com/openapi.json
   ```

4. **Spec behind auth** — download the spec first, then pass the local file:

   ```bash
   $ curl -H "Authorization: Bearer $TOKEN" https://api.example.com/openapi.json -o spec.json
   $ phlatline scan spec.json
   ```

---

### Schema not found (404)

**Symptom** — the URL resolves but returns a 404 or HTML error page:

```
$ phlatline scan https://api.example.com/openapi.json
▸ Loading schema: https://api.example.com/openapi.json
SchemaLoadError: URL returned non-schema content (content-type: text/html; status 404).
  Hint: The URL may point to a login page or a CDN 404 page, not a spec.
```

**Causes and fixes:**

1. **Wrong path** — common spec paths to try:

   ```bash
   $ phlatline scan https://api.example.com/openapi.yaml
   $ phlatline scan https://api.example.com/v1/openapi.json
   $ phlatline scan https://api.example.com/swagger.json
   $ phlatline scan https://api.example.com/docs/openapi.json
   ```

2. **Spec only served in a browser session** — download it manually via the developer tools
   Network tab (look for an XHR request to `/openapi.json` or `/api-docs`), save the file,
   then pass the local path to `phlatline scan`.

3. **Redirection to a login page** — the spec endpoint requires authentication.
   Add a `--config auth.yaml` pointing to your credentials (see the auth section below).

---

### Auth failures

**Symptom** — the CLI loads the schema but every test case returns 401 or 403:

```
$ phlatline scan openapi.yaml --config auth.yaml
▸ Loading schema: openapi.yaml
▸ Base URL: https://api.example.com
▸ Auth: bearer
▸ 12 cases executed in 1.43s
──────────────────────────────────────────────────────
PASS: 0   FAIL: 12   ERROR: 0   SKIP: 0
```

Or the config file itself is rejected at load time:

```
$ phlatline scan openapi.yaml --config auth.yaml
[!] AuthError: unsupported auth type "apikey" — use "api_key"
```

**Auth config format** (`auth.yaml`):

```yaml
# Bearer token
type: bearer
token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# API key in header
type: api_key
name: X-API-Key
location: header
value: "sk_live_abc123"

# API key in query string
type: api_key
name: api_key
location: query
value: "sk_live_abc123"

# HTTP Basic
type: basic
username: "alice"
password: "hunter2"
```

**Valid `type` values:** `bearer`, `basic`, `api_key`, `custom`, `oauth2`

**Fixes:**

1. Verify the token is valid — copy it from your API client and test with `curl`:

   ```bash
   $ curl -H "Authorization: Bearer $TOKEN" https://api.example.com/v1/me
   ```

2. Check the key spelling in `auth.yaml` — use `api_key` (with underscore), not `apikey`.

3. If your token rotates (OAuth2 client credentials), use the `oauth2` type:

   ```yaml
   type: oauth2
   token_url: "https://auth.example.com/oauth/token"
   client_id: "my-client"
   client_secret: "my-secret"
   scopes: ["read:api"]
   ```

---

### Unsupported Python versions

**Symptom** — `pip install` fails with a Python version error:

```
$ python --version
Python 3.9.18

$ pip install phlatline-core
ERROR: Package 'phlatline-core' requires a different Python: 3.9.18 not in '>=3.11'
```

**Fix** — install Python 3.11 or newer.

Recommended options:

- **pyenv** (Linux/macOS):

  ```bash
  $ pyenv install 3.11
  $ pyenv local 3.11
  $ pip install phlatline-core
  ```

- **Official installer** — download from <https://python.org/downloads/>.

- **Docker** — run Phlatline in a container without touching your system Python:

  ```bash
  $ docker run --rm -v "$(pwd):/work" -w /work python:3.11-slim \
      sh -c "pip install phlatline-core && phlatline scan openapi.yaml"
  ```

**Note on Python 3.13:** phlatline-core supports 3.13 but the ecosystem is newer —
if you hit unexpected dependency errors, try 3.11 or 3.12 first.

---

## Still stuck?

Open an issue at <https://github.com/snoodleboot-io/phlatline-core/issues> and include:

- `phlatline --version` output
- `python --version` output
- The full error message (redact any secrets)
