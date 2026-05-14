Feature: Schema loader accepts multiple OpenAPI formats
  The CLI's first job is to load an OpenAPI/Swagger spec from a file or URL.
  It must handle Swagger 2.0, OpenAPI 3.0, and OpenAPI 3.1, in both JSON
  and YAML formats.

  Scenario: Swagger 2.0 JSON file loads successfully
    Given a fixture spec at "tests/fixtures/specs/swagger_2_0.json"
    When the schema is loaded
    Then the schema contains a "swagger" key with value "2.0"
    And the schema contains at least one path

  Scenario: OpenAPI 3.0 YAML file loads successfully
    Given a fixture spec at "tests/fixtures/specs/openapi_3_0.yaml"
    When the schema is loaded
    Then the schema contains an "openapi" key starting with "3."
    And the schema contains at least one path

  Scenario: OpenAPI 3.1 JSON file loads successfully
    Given a fixture spec at "tests/fixtures/specs/openapi_3_1.json"
    When the schema is loaded
    Then the schema contains an "openapi" key starting with "3.1"
    And the schema contains at least one path

  Scenario: Invalid file raises SchemaLoadError
    Given a non-existent file "tests/fixtures/specs/does_not_exist.json"
    When the schema is loaded
    Then a SchemaLoadError is raised

  Scenario: Base URL is derived from schema servers
    Given an OpenAPI 3.0 schema with a server "https://api.example.com/v1"
    When resolve_base_url is called without an override
    Then the resolved URL is "https://api.example.com/v1"

  Scenario: Base URL override wins over schema servers
    Given an OpenAPI 3.0 schema with a server "https://api.example.com/v1"
    When resolve_base_url is called with override "https://staging.example.com"
    Then the resolved URL is "https://staging.example.com"
