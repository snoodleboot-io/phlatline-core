Feature: Sequential executor runs test cases and captures redacted results
  The OSS executor runs one case at a time using sync httpx. It records
  the request and response (redacted), measures duration, and returns a
  TestResult for each TestCase.

  Scenario: Executor records a successful request
    Given a mocked server that returns 200 with body {"ok": true}
    And a TestCase for GET /ping
    When the executor runs the case
    Then the result status_code is 200
    And the result status is "pass"
    And the result duration_ms is greater than zero

  Scenario: Executor masks credentials in recorded request
    Given a mocked server that returns 200
    And a TestCase for GET /ping with Authorization header "Bearer sk_secret_abcdefghij"
    When the executor runs the case
    Then the recorded request Authorization header is masked

  Scenario: Executor marks a 4xx response as failing when happy path expected
    Given a mocked server that returns 400 with body {"error": "bad"}
    And a happy-path TestCase for GET /ping
    When the executor runs the case
    Then the result status is "fail"
    And the result status_code is 400

  Scenario: Executor handles network errors gracefully
    Given a mocked server that raises a connection error
    And a TestCase for GET /ping
    When the executor runs the case
    Then the result status is "error"
    And the result error message is non-empty
