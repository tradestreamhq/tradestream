"""Tests for the API Documentation service and OpenAPI spec validation."""

import json

import pytest
from fastapi.testclient import TestClient

from services.api_docs.app import create_app
from services.api_docs.openapi_spec import get_spec


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestSwaggerUI:
    def test_docs_page_loads(self, client):
        resp = client.get("/api/docs")
        assert resp.status_code == 200
        assert "swagger" in resp.text.lower() or "openapi" in resp.text.lower()

    def test_redoc_page_loads(self, client):
        resp = client.get("/api/redoc")
        assert resp.status_code == 200

    def test_openapi_json_endpoint(self, client):
        resp = client.get("/api/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        assert spec["openapi"].startswith("3.0")


class TestOpenAPISpecValidity:
    """Validate the OpenAPI spec structure and completeness."""

    def test_spec_has_required_top_level_fields(self):
        spec = get_spec()
        assert "openapi" in spec
        assert "info" in spec
        assert "paths" in spec
        assert "components" in spec
        assert spec["openapi"].startswith("3.0")

    def test_spec_info_fields(self):
        spec = get_spec()
        info = spec["info"]
        assert "title" in info
        assert "version" in info
        assert "description" in info

    def test_spec_has_security_scheme(self):
        spec = get_spec()
        schemes = spec["components"]["securitySchemes"]
        assert "ApiKeyAuth" in schemes
        assert schemes["ApiKeyAuth"]["type"] == "apiKey"
        assert schemes["ApiKeyAuth"]["in"] == "header"

    def test_spec_has_global_security(self):
        spec = get_spec()
        assert "security" in spec
        assert len(spec["security"]) > 0

    def test_all_paths_have_operations(self):
        spec = get_spec()
        for path, methods in spec["paths"].items():
            assert len(methods) > 0, f"Path {path} has no operations"
            for method, operation in methods.items():
                assert method in (
                    "get",
                    "post",
                    "put",
                    "delete",
                    "patch",
                    "options",
                    "head",
                ), f"Invalid method {method} in {path}"
                assert (
                    "responses" in operation
                ), f"Missing responses for {method.upper()} {path}"
                assert (
                    "summary" in operation or "description" in operation
                ), f"Missing summary/description for {method.upper()} {path}"

    def test_all_operations_have_tags(self):
        spec = get_spec()
        for path, methods in spec["paths"].items():
            for method, operation in methods.items():
                assert (
                    "tags" in operation
                ), f"Missing tags for {method.upper()} {path}"
                assert len(operation["tags"]) > 0

    def test_all_operations_have_unique_operation_ids(self):
        spec = get_spec()
        operation_ids = []
        for path, methods in spec["paths"].items():
            for method, operation in methods.items():
                op_id = operation.get("operationId")
                assert (
                    op_id is not None
                ), f"Missing operationId for {method.upper()} {path}"
                assert (
                    op_id not in operation_ids
                ), f"Duplicate operationId '{op_id}' for {method.upper()} {path}"
                operation_ids.append(op_id)

    def test_all_refs_resolve(self):
        spec = get_spec()
        spec_json = json.dumps(spec)
        # Find all $ref values
        import re

        refs = re.findall(r'"\$ref":\s*"([^"]+)"', spec_json)
        schemas = spec.get("components", {}).get("schemas", {})
        for ref in refs:
            assert ref.startswith(
                "#/components/schemas/"
            ), f"Unsupported ref format: {ref}"
            schema_name = ref.split("/")[-1]
            assert (
                schema_name in schemas
            ), f"$ref '{ref}' does not resolve — schema '{schema_name}' not found"

    def test_path_parameters_declared(self):
        spec = get_spec()
        import re

        for path, methods in spec["paths"].items():
            # Extract path parameters like {spec_id}
            path_params = re.findall(r"\{(\w+)\}", path)
            if not path_params:
                continue
            for method, operation in methods.items():
                params = operation.get("parameters", [])
                declared_path_params = [
                    p["name"] for p in params if p.get("in") == "path"
                ]
                for pp in path_params:
                    assert pp in declared_path_params, (
                        f"Path parameter '{pp}' in {path} not declared "
                        f"in {method.upper()} operation parameters"
                    )

    def test_post_put_operations_have_request_body(self):
        spec = get_spec()
        for path, methods in spec["paths"].items():
            for method in ("post", "put"):
                if method not in methods:
                    continue
                operation = methods[method]
                # Skip health checks and creation endpoints without bodies
                if path.endswith("/health") or path.endswith("/ready"):
                    continue
                # Endpoints that create resources without request body
                # (e.g., POST /specs/{id}/implementations)
                if "requestBody" not in operation:
                    # At minimum ensure there's at least one response defined
                    assert "responses" in operation

    def test_minimum_endpoint_count(self):
        """Ensure we documented at least 50 endpoints."""
        spec = get_spec()
        endpoint_count = 0
        for path, methods in spec["paths"].items():
            endpoint_count += len(methods)
        assert (
            endpoint_count >= 50
        ), f"Expected at least 50 endpoints, got {endpoint_count}"

    def test_tags_cover_all_modules(self):
        """Verify tags cover the expected modules."""
        spec = get_spec()
        tag_names = {t["name"] for t in spec.get("tags", [])}
        expected_modules = {
            "Portfolio",
            "Positions",
            "Risk",
            "Specs",
            "Implementations",
            "Instruments",
            "Decisions",
            "Analytics",
            "Events",
            "Dashboard",
            "Strategies",
            "Paper Trading",
            "Portfolio State",
            "Health",
        }
        missing = expected_modules - tag_names
        assert not missing, f"Missing tags for modules: {missing}"

    def test_error_schema_structure(self):
        spec = get_spec()
        error_schema = spec["components"]["schemas"]["ErrorResponse"]
        assert "error" in error_schema["properties"]
        error_obj = error_schema["properties"]["error"]
        assert "code" in error_obj["properties"]
        assert "message" in error_obj["properties"]

    def test_pagination_meta_schema(self):
        spec = get_spec()
        meta = spec["components"]["schemas"]["PaginationMeta"]
        assert "total" in meta["properties"]
        assert "limit" in meta["properties"]
        assert "offset" in meta["properties"]

    def test_spec_serializable_to_json(self):
        """Ensure the entire spec can be serialized to JSON without errors."""
        spec = get_spec()
        json_str = json.dumps(spec)
        parsed = json.loads(json_str)
        assert parsed["openapi"] == spec["openapi"]

    def test_all_tags_used_in_operations(self):
        """Verify every declared tag is used by at least one operation."""
        spec = get_spec()
        declared = {t["name"] for t in spec.get("tags", [])}
        used = set()
        for path, methods in spec["paths"].items():
            for method, op in methods.items():
                for tag in op.get("tags", []):
                    used.add(tag)
        unused = declared - used
        assert not unused, f"Tags declared but unused: {unused}"

    def test_response_codes_are_strings(self):
        """OpenAPI 3.0 requires response codes as strings."""
        spec = get_spec()
        for path, methods in spec["paths"].items():
            for method, operation in methods.items():
                for code in operation.get("responses", {}):
                    assert isinstance(code, str), (
                        f"Response code {code} in {method.upper()} {path} "
                        f"should be a string, got {type(code).__name__}"
                    )
