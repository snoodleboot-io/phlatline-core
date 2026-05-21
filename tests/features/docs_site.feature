Feature: Docs site is live, searchable, on-brand

  Scenario: Docs site builds with required navigation links
    Given mkdocs is installed with the Material theme
    When "mkdocs build --strict" runs in the package directory
    Then site/index.html is created
    And it contains a link labelled "Quickstart"
    And it contains a link labelled "CLI reference"
    And it contains a link labelled "FAQ"

  Scenario: Search index includes expected content
    Given the docs site has been built
    When I inspect the search index
    Then it contains an entry mentioning "boundary test"

  Scenario: CLI reference auto-regenerates from Click --help
    Given the phlatline-core package is installed
    When the CLI reference generator script runs
    Then a Markdown file is produced
    And it contains documentation for the "scan" command
    And it contains the "--base-url" option

  Scenario: Mobile layout is configured for responsive rendering
    Given mkdocs.yml exists in the package root
    When I inspect its configuration
    Then the Material theme is declared
    And responsive navigation features are enabled
