# phlatline-core

OpenAPI-driven API diagnostic CLI.

## Status

This is the S0.1 scaffolding — test stack only. Feature code arrives in E1.

## Quickstart

```bash
pip install -e .[dev]
pytest                  # runs sample Gherkin scenarios
phlatline --help         # CLI stub
```

## Testing

Strict ATDD + TDD per `docs/decisions/ADR-002-testing-discipline.md`.
Every story begins with failing Gherkin scenarios in `tests/features/`
and passes when they go green.

## License

Business Source License 1.1 · auto-converts to Apache 2.0 after 4 years.
