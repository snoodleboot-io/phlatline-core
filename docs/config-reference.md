# Configuration

## `phlatline.yaml` — project file

Use a project file to scan multiple targets (environments, services) in one run.

### Full example

```yaml
name: my-api

targets:
  - name: prod
    schema: https://api.example.com/openapi.json
    base_url: https://api.example.com
    auth:
      type: bearer
      token: "${PROD_API_TOKEN}"

  - name: staging
    schema: ./openapi.yaml
    base_url: https://staging.example.com
    auth:
      type: bearer
      token: "${STAGING_API_TOKEN}"
    fuzz: false

  - name: local
    schema: ./openapi.yaml
    base_url: http://localhost:8000
```

### Fields

#### `name` (required)

Project name. Used in report filenames and the project summary.

#### `targets` (required)

List of targets to scan.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Target name (used in report dir slug) |
| `schema` | string | yes | Path to OpenAPI spec file, or HTTPS URL |
| `base_url` | string | no | Override the base URL from the spec |
| `auth` | object | no | Auth config (see below) |
| `fuzz` | bool | no | Enable fuzzing for this target (default: true) |

---

## Auth config

Auth can be specified inline in `phlatline.yaml` (per-target) or in a standalone file
passed via `--config`.

### Bearer token

```yaml
type: bearer
token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### API key in header

```yaml
type: api_key
name: X-API-Key
location: header
value: "sk_live_abc123"
```

### API key in query string

```yaml
type: api_key
name: api_key
location: query
value: "sk_live_abc123"
```

### API key in cookie

```yaml
type: api_key
name: session
location: cookie
value: "my-session-token"
```

### HTTP Basic

```yaml
type: basic
username: "alice"
password: "hunter2"
```

### OAuth2 client credentials

```yaml
type: oauth2
token_url: "https://auth.example.com/oauth/token"
client_id: "my-client"
client_secret: "my-secret"
scopes:
  - "read:api"
  - "write:api"
```

### Custom headers

```yaml
type: custom
headers:
  X-Tenant-ID: "acme"
  X-Internal-Key: "supersecret"
```

### Valid `type` values

`bearer` · `basic` · `api_key` · `oauth2` · `custom`

---

## Environment variable substitution

Auth values support `${ENV_VAR}` substitution:

```yaml
auth:
  type: bearer
  token: "${API_TOKEN}"
```

Set the variable before running:

```bash
export API_TOKEN="sk_live_abc123"
phlatline scan openapi.yaml --config auth.yaml
```

This keeps secrets out of config files committed to version control.

---

## Settings

Phlatline reads settings from environment variables with the `PHLATLINE_` prefix.

| Variable | Default | Description |
|---|---|---|
| `PHLATLINE_REPORT_OUTPUT_DIR` | `./phlatline_results` | Base directory for all reports |
| `PHLATLINE_FUZZ_EXAMPLES_PER_OPERATION` | `10` | Hypothesis examples per endpoint |
| `PHLATLINE_EXECUTION_VERIFY_SSL` | `true` | Verify TLS certificates |
| `PHLATLINE_CLOUD_TOKEN` | _(unset)_ | Upload runs to Phlatline Cloud (EE feature) |
