Feature: Credential redaction prevents secret leakage
  Phlatline records request/response data for every test case. If that data
  contains credentials, we must mask them before persisting, logging, or
  displaying the results. This applies recursively to nested structures.

  Scenario: Authorization header is masked preserving first and last 4 chars
    Given a request with Authorization "Bearer sk_live_abc123xyz"
    When redact_headers processes it
    Then the result for "Authorization" starts with "Bear"
    And the result for "Authorization" ends with "xyz"
    And the result for "Authorization" contains a mask character

  Scenario: Short cookie value is fully masked
    Given a request with Cookie "short"
    When redact_headers processes it
    Then the result for "Cookie" is exactly "***"

  Scenario: Long cookie value is partially masked
    Given a request with Cookie "session_abc123_xyz789"
    When redact_headers processes it
    Then the result for "Cookie" starts with "sess"
    And the result for "Cookie" ends with "z789"

  Scenario: Credential-bearing header names are detected by substring
    When I check header names for credential-ness
    Then "x-api-key" is identified as a credential
    And "api_token" is identified as a credential
    And "x-auth-token" is identified as a credential
    And "content-type" is not identified as a credential

  Scenario: Query parameter credentials are partially masked
    Given query params with "api_key=secret_value_1234567890" and "page=2"
    When redact_query_params processes them
    Then the "api_key" value starts with "secr"
    And the "page" value is preserved as "2"

  Scenario: JSON body credentials are masked recursively
    Given a body with {"password": "hunter2hunter2", "email": "u@x.com", "nested": {"api_key": "sk_live_abc_1234567890"}}
    When redact_body processes it
    Then the "password" field value starts with "hunt"
    And the "email" field value is preserved
    And the nested "api_key" field value starts with "sk_l"

  Scenario: Stripe-shaped secret value is detected
    When I check "sk_live_abcdefghijklmnop" for secret-shape
    Then it is identified as a secret
    When I check "hello world" for secret-shape
    Then it is not identified as a secret

  Scenario: Response preview with Stripe key is sanitized
    Given a response text containing "token=sk_live_abcdefghijklmnop and other stuff"
    When redact_response_preview processes it
    Then the resulting text does not contain "sk_live_abcdefghijklmnop"
    And the resulting text contains "REDACTED"
