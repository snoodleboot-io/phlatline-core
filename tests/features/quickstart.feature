Feature: A new user gets to their first diagnostic in under five minutes

  Scenario: README quickstart works verbatim on a clean machine
    Given phlatline-core is installed and a local spec is available
    When the user runs the quickstart scan
    Then the command exits with code 0
    And an HTML report file is created in the output directory

  Scenario: Troubleshooting covers the common failure modes
    Given INSTALL.md exists in the package root
    When I inspect its contents
    Then it includes a section for network errors
    And it includes a section for schema 404s
    And it includes a section for auth failures
    And it includes a section for unsupported Python versions
    And each section has a reproducible command and expected error
