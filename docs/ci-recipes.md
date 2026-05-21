# CI recipes

Run Phlatline on every pull request to catch API regressions before they ship.

## GitHub Actions

### Single-target scan on PR

```yaml
# .github/workflows/api-diagnostic.yml
name: API Diagnostic

on:
  pull_request:
  push:
    branches: [main]

jobs:
  diagnostic:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install phlatline-core
        run: pip install phlatline-core

      - name: Run diagnostic
        env:
          API_TOKEN: ${{ secrets.API_TOKEN }}
        run: |
          phlatline scan https://api.example.com/openapi.json \
            --config auth.yaml \
            --output-dir ./reports

      - name: Upload reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: phlatline-reports
          path: ./reports/
```

### Multi-target project

```yaml
      - name: Run multi-target diagnostic
        run: phlatline project phlatline.yaml --output-dir ./reports
```

### Matrix across environments

```yaml
jobs:
  diagnostic:
    strategy:
      matrix:
        env: [staging, prod]
    steps:
      - name: Scan ${{ matrix.env }}
        env:
          API_TOKEN: ${{ secrets[format('{0}_API_TOKEN', matrix.env)] }}
        run: |
          phlatline scan ${{ matrix.env == 'prod' && 'https://api.example.com/openapi.json' || 'https://staging.example.com/openapi.json' }} \
            --config auth.yaml \
            --output-dir ./reports/${{ matrix.env }}
```

---

## GitLab CI

```yaml
# .gitlab-ci.yml
api-diagnostic:
  stage: test
  image: python:3.12-slim
  before_script:
    - pip install phlatline-core
  script:
    - phlatline scan https://api.example.com/openapi.json
        --config auth.yaml
        --output-dir ./reports
  artifacts:
    when: always
    paths:
      - reports/
    expire_in: 7 days
  variables:
    API_TOKEN: $API_TOKEN
```

---

## CircleCI

```yaml
# .circleci/config.yml
version: 2.1

jobs:
  api-diagnostic:
    docker:
      - image: cimg/python:3.12
    steps:
      - checkout
      - run:
          name: Install phlatline-core
          command: pip install phlatline-core
      - run:
          name: Run API diagnostic
          command: |
            phlatline scan https://api.example.com/openapi.json \
              --config auth.yaml \
              --output-dir ./reports
      - store_artifacts:
          path: reports/

workflows:
  main:
    jobs:
      - api-diagnostic
```

---

## Tips

### Only scan on relevant changes

Gate the diagnostic on changes to your API spec or backend code:

```yaml
# GitHub Actions
on:
  pull_request:
    paths:
      - 'api/**'
      - 'openapi.yaml'
      - 'backend/**'
```

### Fail gracefully on non-critical APIs

If a staging API is allowed to be flaky, use `continue-on-error`:

```yaml
      - name: Run diagnostic (non-blocking)
        continue-on-error: true
        run: phlatline scan staging-openapi.yaml
```

### Cache pip installs

```yaml
      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-phlatline-${{ hashFiles('**/requirements*.txt') }}

      - run: pip install phlatline-core
```

### Upload to Phlatline Cloud

Set `PHLATLINE_CLOUD_TOKEN` to have runs automatically uploaded to the dashboard:

```yaml
      - name: Run and upload
        env:
          PHLATLINE_CLOUD_TOKEN: ${{ secrets.PHLATLINE_CLOUD_TOKEN }}
        run: phlatline scan openapi.yaml
```
