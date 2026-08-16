# FAQ

## General

### What does "boundary test" mean?

A boundary test exercises the edges of your API's declared schema. For example, if an
endpoint accepts an integer `amount` with `minimum: 1` and `maximum: 999999`, Phlatline
sends `0`, `1`, `999999`, `1000000`, `MAX_INT32`, and `-1` — values just inside and
outside the declared range. These cases find validation gaps that aren't visible from
a typical happy-path integration test.

### What does "fuzz" mean?

The fuzz stage uses [Hypothesis](https://hypothesis.readthedocs.io/) to generate random
valid inputs within your schema's type constraints. This finds unexpected 500 errors
triggered by edge-case inputs your team never thought to test. Fuzzing runs after the
happy-path and boundary cases.

It requires the optional `[fuzz]` extra (`pip install 'phlatline-core[fuzz]'`). Without it the
stage reports itself as skipped and the rest of the scan runs normally.

### Does Phlatline modify production data?

Yes, it sends real HTTP requests to whatever `base_url` you point it at. On `prod`,
those requests will create, update, or delete real records. We recommend:

- Running against `staging` by default
- Using a dedicated test tenant or workspace
- Using `--no-fuzz` for a lighter touch on sensitive environments

### How long does a scan take?

For a typical API with 20–50 operations, a full scan (with fuzzing) takes 30–120 seconds.
Use `--no-fuzz` to skip the Hypothesis stage and cut runtime to 5–15 seconds.

---

## Schema loading

### Why does Phlatline say "URL returned non-schema content"?

The URL you passed either returned a 404, redirected to a login page, or returned HTML
instead of JSON/YAML. Common fixes:

- Check the actual spec path: try `/openapi.json`, `/swagger.json`, `/api-docs`, or `/v1/openapi.yaml`
- If the spec is behind auth, download it first with `curl -H "Authorization: Bearer $TOKEN" <url> -o spec.json`
- Use the browser devtools Network tab to find the XHR request that fetches the spec

### Does Phlatline resolve `$ref` pointers?

Yes. Phlatline follows all `$ref` pointers within the spec, including cross-file refs, before
generating test cases. If a `$ref` points to an unreachable URL, you'll see a `SchemaLoadError`.

### Is Swagger 2.0 supported?

Yes — Swagger 2.0, OpenAPI 3.0, and OpenAPI 3.1 are all supported in both JSON and YAML format.

---

## Authentication

### Where do I put my API key?

Create an `auth.yaml` file:

```yaml
type: api_key
name: X-API-Key
location: header
value: "sk_live_abc123"
```

Then pass it: `phlatline scan openapi.yaml --config auth.yaml`

See [Configuration](config-reference.md) for all auth types.

### Can I use environment variables for secrets?

Yes. Use `${MY_VAR}` in your auth config:

```yaml
type: bearer
token: "${API_TOKEN}"
```

### Why do all my tests fail with 401?

Check that:

1. The token in `auth.yaml` is valid and hasn't expired
2. The `type` field is correct (`bearer`, not `jwt` or `token`)
3. The auth is applied to the right header (check `--config auth.yaml` is being passed)
4. The API actually reads the `Authorization` header (some APIs use `X-Auth-Token`)

---

## Reports

### Where are reports written?

By default, to `./phlatline_results/{target-name}/`. Override with `--output-dir`.

Each target gets two files:

- `report.html` — human-readable report with expandable test results
- `results.json` — machine-readable results for CI processing

### How do I read the HTML report?

Open `report.html` in any browser. The report shows:

- Summary stats (pass/fail/error/skip counts)
- Per-category breakdown (happy path, boundary, fuzz, auth missing)
- Expandable rows for each test case with the request and response

### Can I integrate the JSON output into my CI pipeline?

Yes. `results.json` contains structured data you can parse with `jq` or any JSON library.
The schema matches the `CompletedRun` Pydantic model in [sdk/models.py](https://github.com/snoodleboot-io/phlatline-core/blob/main/phlatline/sdk/models.py).

---

## Licensing

### Is phlatline-core free to use?

Phlatline is licensed under the **Business Source License 1.1 (BSL 1.1)**. You may use
it freely for:

- Development and testing environments
- Internal tooling
- Non-commercial projects

The Additional Use Grant in `LICENSE` covers all non-production use cases.
The license auto-converts to **Apache 2.0** on **2029-05-01**.

For commercial production use (running the CLI against production APIs as a service),
contact [hi@phlatline.dev](mailto:hi@phlatline.dev).

### What's in Phlatline Cloud (EE)?

The OSS CLI handles everything locally. Phlatline Cloud adds:

- Run history and trends dashboard
- Scheduled diagnostics (cron)
- Slack and webhook alerts on spike events
- Public status pages
- Team collaboration

See [phlatline.dev](https://phlatline.dev) for pricing.
