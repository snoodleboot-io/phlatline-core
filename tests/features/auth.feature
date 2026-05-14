Feature: Auth strategies inject credentials into requests
  Phlatline supports multiple auth schemes. Each strategy takes a configured
  credential and injects it into outgoing requests in the correct way
  (header, query param, basic-auth tuple, etc.).

  Scenario: Bearer strategy adds Authorization header
    Given a bearer auth context with token "sk_test_abc123"
    When the strategy is applied to an empty request
    Then the headers include "Authorization: Bearer sk_test_abc123"

  Scenario: Basic strategy adds Authorization header with base64 creds
    Given a basic auth context with username "alice" and password "s3cret"
    When the strategy is applied to an empty request
    Then the headers include an "Authorization" header starting with "Basic "

  Scenario: API key strategy in header
    Given an api-key auth context with key "api_abc" in header "X-API-Key"
    When the strategy is applied to an empty request
    Then the headers include "X-API-Key: api_abc"

  Scenario: API key strategy in query parameter
    Given an api-key auth context with key "api_xyz" in query "api_key"
    When the strategy is applied to an empty request
    Then the query params include "api_key=api_xyz"

  Scenario: No auth config produces a pass-through strategy
    Given no auth configuration
    When the strategy is applied to an empty request
    Then the request is unchanged
