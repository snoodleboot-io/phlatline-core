Feature: Reporter produces JSON and HTML output
  After execution, phlatline writes two artifacts: a structured JSON file
  for machine consumption, and an HTML report styled with the brand
  aesthetic for humans.

  Scenario: Summarize counts results by status
    Given a list of results with 3 passing, 2 failing, 1 error
    When summarize is called
    Then the summary total is 6
    And the summary pass_count is 3
    And the summary fail is 2
    And the summary error is 1

  Scenario: write_json produces a readable JSON file
    Given a list of 2 passing results
    When write_json writes to a temp path
    Then the file exists
    And the file parses as JSON
    And the parsed JSON has a "results" array of length 2
    And the parsed JSON has a "meta" object

  Scenario: write_html produces an HTML file with brand markers
    Given a list of 2 passing results
    When write_html writes to a temp path
    Then the file exists
    And the file contents start with "<!DOCTYPE html>"
    And the file contents contain "phlatline"

  Scenario: HTML output includes CSP header meta tag
    Given a list of 1 passing result
    When write_html writes to a temp path
    Then the file contents contain "Content-Security-Policy"
