Feature: Optional fuzzing dependency ships as an installable extra

  Fuzzing is an advertised capability but depends on Schemathesis, which is not
  a hard dependency. Users need one obvious, documented way to install it.

  Scenario: The fuzz extra declares Schemathesis
    Given pyproject.toml exists in the package root
    When I inspect its optional dependencies
    Then a "fuzz" extra is declared
    And the "fuzz" extra requires "schemathesis"

  Scenario: Skipping fuzzing points at the fuzz extra
    Given Schemathesis is not installed
    When fuzzing runs against a schema
    Then no fuzz results are produced
    And the warning tells the user to install "phlatline-core[fuzz]"
