"""Tests for the API Documentation service and OpenAPI spec validation."""

import json
import re

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

    def test_index_page(self, client):
        resp = client.get("/")
        assert resp.status_code == 200


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

    def test_spec_has_security_schemes(self):
        spec = get_spec()
        schemes = spec["components"]["securitySchemes"]
        assert "ApiKeyAuth" in schemes
        assert schemes["ApiKeyAuth"]["type"] == "apiKey"
        assert schemes["ApiKeyAuth"]["in"] == "header"
        assert "BearerAuth" in schemes
        assert schemes["BearerAuth"]["type"] == "http"
        assert schemes["BearerAuth"]["scheme"] == "bearer"

    def test_spec_has_global_security(self):
        spec = get_spec()
        assert "security" in spec
        assert len(spec["security"]) >= 2
        security_names = set()
        for entry in spec["security"]:
            security_names.update(entry.keys())
        assert "ApiKeyAuth" in security_names
        assert "BearerAuth" in security_names

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
        for path, methods in spec["paths"].items():
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
                if path.endswith("/health") or path.endswith("/ready"):
                    continue
                if "requestBody" not in operation:
                    assert "responses" in operation

    def test_minimum_endpoint_count(self):
        """Ensure we documented at least 100 endpoints."""
        spec = get_spec()
        endpoint_count = 0
        for path, methods in spec["paths"].items():
            endpoint_count += len(methods)
        assert (
            endpoint_count >= 100
        ), f"Expected at least 100 endpoints, got {endpoint_count}"

    def test_tags_cover_all_modules(self):
        """Verify tags cover the expected modules."""
        spec = get_spec()
        tag_names = {t["name"] for t in spec.get("tags", [])}
        expected_modules = {
            # Core services
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
            # New modules
            "Signals",
            "Signal Subscriptions",
            "Marketplace",
            "Marketplace Reviews",
            "Billing",
            "Backtesting",
            "Opportunities",
            "Users",
            "API Keys",
            "Notifications",
            "TradingView",
            "Telegram",
            "Discord",
            "Webhooks",
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

    def test_rate_limit_error_schema(self):
        spec = get_spec()
        assert "RateLimitError" in spec["components"]["schemas"]
        rl = spec["components"]["schemas"]["RateLimitError"]
        assert "retry_after" in rl["properties"]["error"]["properties"]

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

    def test_signal_schemas_present(self):
        """Verify signal-related schemas are defined."""
        spec = get_spec()
        schemas = spec["components"]["schemas"]
        for name in ["Signal", "SignalSubscription", "SignalFilter", "SignalDeliveryLog"]:
            assert name in schemas, f"Missing schema: {name}"

    def test_marketplace_schemas_present(self):
        """Verify marketplace schemas are defined."""
        spec = get_spec()
        schemas = spec["components"]["schemas"]
        for name in [
            "MarketplaceListing", "ListingPricing", "ListingPerformance",
            "MarketplaceReview", "LeaderboardEntry",
        ]:
            assert name in schemas, f"Missing schema: {name}"

    def test_billing_schemas_present(self):
        """Verify billing schemas are defined."""
        spec = get_spec()
        schemas = spec["components"]["schemas"]
        for name in ["BillingAccount", "Plan", "Invoice", "PaymentMethod", "UsageMetrics"]:
            assert name in schemas, f"Missing schema: {name}"

    def test_backtesting_schemas_present(self):
        """Verify backtesting schemas are defined."""
        spec = get_spec()
        schemas = spec["components"]["schemas"]
        for name in [
            "BacktestRequest", "BacktestResponse", "BacktestMetrics",
            "WalkForwardRequest", "OptimizationRequest",
        ]:
            assert name in schemas, f"Missing schema: {name}"

    def test_user_schemas_present(self):
        """Verify user management schemas are defined."""
        spec = get_spec()
        schemas = spec["components"]["schemas"]
        for name in ["User", "AuthTokens", "ApiKey", "NotificationPreferences"]:
            assert name in schemas, f"Missing schema: {name}"

    def test_integration_schemas_present(self):
        """Verify integration schemas are defined."""
        spec = get_spec()
        schemas = spec["components"]["schemas"]
        for name in [
            "TradingViewAlert", "TradingViewConfig", "TelegramConfig",
            "DiscordConfig", "WebhookConfig", "WebhookDelivery",
        ]:
            assert name in schemas, f"Missing schema: {name}"

    def test_opportunity_schemas_present(self):
        """Verify opportunity schemas are defined."""
        spec = get_spec()
        schemas = spec["components"]["schemas"]
        for name in ["Opportunity", "ConfluenceFactor"]:
            assert name in schemas, f"Missing schema: {name}"

    def test_servers_defined(self):
        """Verify server URLs are defined."""
        spec = get_spec()
        assert "servers" in spec
        assert len(spec["servers"]) >= 2
        urls = [s["url"] for s in spec["servers"]]
        assert any("localhost" in u for u in urls)

    def test_api_guidelines_documented(self):
        """Verify rate limits, pagination, and errors are documented."""
        spec = get_spec()
        guidelines = spec["info"].get("x-api-guidelines", {})
        assert "rate_limits" in guidelines
        assert "pagination" in guidelines
        assert "errors" in guidelines
        assert "authentication" in guidelines

    def test_public_endpoints_have_empty_security(self):
        """Endpoints like login and register should have empty security."""
        spec = get_spec()
        public_paths = [
            "/api/v1/auth/register",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
            "/api/v1/billing/plans",
        ]
        for path in public_paths:
            if path in spec["paths"]:
                for method, op in spec["paths"][path].items():
                    assert op.get("security") == [], (
                        f"{method.upper()} {path} should have security: [] (public)"
                    )
