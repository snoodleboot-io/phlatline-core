Feature: Test case generator produces diverse cases from OpenAPI specs
  For each endpoint, phlatline generates test cases across multiple categories.
  The OSS set includes happy path, auth (missing/invalid credentials),
  boundary (edge-value inputs), and negative (malformed inputs).

  Background:
    Given the OpenAPI 3.0 fixture spec is loaded

  Scenario: Generator produces happy-path cases
    When generate_test_cases runs for the whole schema
    Then at least one case has category "happy"

  Scenario: Generator produces auth cases for secured endpoints
    When generate_test_cases runs for the whole schema
    Then at least one case has category "auth"

  Scenario: Generator produces boundary cases for constrained parameters
    When generate_test_cases runs for the whole schema
    Then at least one case has category "boundary"

  Scenario: Generator produces negative cases
    When generate_test_cases runs for the whole schema
    Then at least one case has category "negative"

  Scenario: Custom generator list restricts output to one category
    Given only the HappyPathGenerator is selected
    When generate_test_cases runs for the whole schema
    Then every case has category "happy"
