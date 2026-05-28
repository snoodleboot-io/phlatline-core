"""Phlatline — OpenAPI-driven API diagnostic tool.

Phlatline loads an OpenAPI schema, generates test cases across multiple
categories (happy path, negative, auth, boundary, fuzz), executes them
against a live target, and reports results.  It is the public entry point
for the ``phlatline-core`` package and re-exports the public version string.

No spikes. No surprises.
"""
__version__ = "3.0.0"
