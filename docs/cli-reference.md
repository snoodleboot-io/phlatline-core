# CLI reference

!!! tip "Auto-generated"
    This page is regenerated from `phlatline --help` on every release.
    Run `python scripts/gen_cli_reference.py` to update it locally.

---

## `phlatline`

```
Usage: phlatline [OPTIONS] COMMAND [ARGS]...

  Phlatline — No spikes. No surprises.

  Use `phlatline scan SCHEMA` to run against a single schema.
  Use `phlatline project FILE` for multi-target runs.

Options:
  -V, --version  Show the version and exit.
  --no-banner    Suppress the CLI banner.
  -h, --help     Show this message and exit.

Commands:
  project  Run a multi-target PROJECT_FILE.
  scan     Run the test suite against a single SCHEMA (file path or URL).
```

---

## `phlatline scan`

```
Usage: phlatline scan [OPTIONS] SCHEMA

  Run the test suite against a single SCHEMA (file path or URL).

Options:
  --base-url TEXT          Override the base URL from the schema servers block.
  --config FILE            Path to auth config (JSON/YAML).
  --output-dir TEXT        Where to write reports (default: ./phlatline_results).
  --no-fuzz                Skip the fuzzing stage (faster runs).
  --fuzz-examples INTEGER  Hypothesis examples per operation (default: 10).
  --no-verify-ssl          Skip TLS certificate verification.
  -h, --help               Show this message and exit.
```

### Options

#### `SCHEMA`

Path to a local OpenAPI/Swagger file, or an HTTPS URL. Accepts:

- `./openapi.yaml`
- `./swagger.json`
- `https://api.example.com/openapi.json`

Swagger 2.0, OpenAPI 3.0, and OpenAPI 3.1 are all supported in JSON or YAML format.

#### `--base-url`

Override the `servers[0].url` from the spec. Useful when the spec says `https://prod.example.com`
but you want to test against `https://staging.example.com`.

```bash
phlatline scan openapi.yaml --base-url https://staging.example.com
```

#### `--config`

Path to an auth config file. See [Configuration](config-reference.md) for the full format.

```bash
phlatline scan openapi.yaml --config auth.yaml
```

#### `--output-dir`

Directory where HTML and JSON reports are written. Created if it doesn't exist.

```bash
phlatline scan openapi.yaml --output-dir ./ci-reports
```

#### `--no-fuzz`

Skip the fuzzing (Hypothesis) stage. Runs faster; still executes happy-path, boundary, and auth-missing cases.

```bash
phlatline scan openapi.yaml --no-fuzz
```

#### `--fuzz-examples`

Number of Hypothesis examples per operation (default: 10). Increase for more thorough fuzzing.

```bash
phlatline scan openapi.yaml --fuzz-examples 50
```

#### `--no-verify-ssl`

Disable TLS certificate verification. Useful for internal APIs with self-signed certificates.

```bash
phlatline scan https://internal-api.corp/openapi.json --no-verify-ssl
```

---

## `phlatline project`

```
Usage: phlatline project [OPTIONS] PROJECT_FILE

  Run a multi-target PROJECT_FILE.

Options:
  --output-dir TEXT  Where to write reports.
  -h, --help         Show this message and exit.
```

### Options

#### `PROJECT_FILE`

Path to a `phlatline.yaml` project file. See [Configuration](config-reference.md) for the schema.

#### `--output-dir`

Override the output directory for all targets. If not set, uses `./phlatline_results/`.

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All tests passed (no failures, no errors) |
| `1` | One or more test failures or execution errors |
| `2` | Fatal error (schema failed to load, bad config, etc.) |
