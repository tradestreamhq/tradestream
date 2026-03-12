"""Tests for the documentation generator."""

import tempfile
from pathlib import Path

import pytest
import yaml

from tools.docgen.generate import (
    extract_indicators,
    generate_all,
    generate_api_reference,
    generate_indicator_reference,
    generate_service_graph,
    generate_strategy_reference,
    load_all_strategies,
    parse_fastapi_routes,
    parse_strategy_yaml,
)


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_strategy():
    return {
        "name": "TEST_STRATEGY",
        "description": "A test strategy",
        "complexity": "SIMPLE",
        "parameterMessageType": "com.test.TestParameters",
        "indicators": [
            {"id": "sma", "type": "SMA", "input": "close", "params": {"period": "${smaPeriod}"}},
            {"id": "ema", "type": "EMA", "input": "close", "params": {"period": "${emaPeriod}"}},
        ],
        "entryConditions": [
            {"type": "CROSSED_UP", "indicator": "sma", "params": {"crosses": "ema"}},
        ],
        "exitConditions": [
            {"type": "CROSSED_DOWN", "indicator": "sma", "params": {"crosses": "ema"}},
        ],
        "parameters": [
            {"name": "smaPeriod", "type": "INTEGER", "min": 5, "max": 50, "defaultValue": 20},
            {"name": "emaPeriod", "type": "INTEGER", "min": 5, "max": 50, "defaultValue": 50},
        ],
    }


@pytest.fixture
def strategies_dir(tmp_dir, sample_strategy):
    """Create a temporary strategies directory with sample YAML files."""
    strat_dir = tmp_dir / "strategies"
    strat_dir.mkdir()
    with open(strat_dir / "test_strategy.yaml", "w") as f:
        yaml.dump(sample_strategy, f)

    second = {
        "name": "RSI_STRATEGY",
        "description": "RSI-based strategy",
        "complexity": "MODERATE",
        "indicators": [
            {"id": "rsi", "type": "RSI", "input": "close", "params": {"period": "${rsiPeriod}"}},
        ],
        "entryConditions": [
            {"type": "UNDER", "indicator": "rsi", "params": {"threshold": "30"}},
        ],
        "exitConditions": [
            {"type": "OVER", "indicator": "rsi", "params": {"threshold": "70"}},
        ],
        "parameters": [
            {"name": "rsiPeriod", "type": "INTEGER", "min": 7, "max": 21, "defaultValue": 14},
        ],
    }
    with open(strat_dir / "rsi_strategy.yaml", "w") as f:
        yaml.dump(second, f)

    return strat_dir


@pytest.fixture
def fastapi_app_file(tmp_dir):
    """Create a temporary FastAPI app.py file."""
    app_code = '''
from fastapi import APIRouter, FastAPI, Query

def create_app():
    app = FastAPI(
        title="Test API",
        root_path="/api/v1/test",
    )

    router = APIRouter(prefix="/items", tags=["Items"])

    @router.get("")
    async def list_items():
        """List all items."""
        return []

    @router.post("")
    async def create_item():
        """Create a new item."""
        return {}

    @router.get("/{item_id}")
    async def get_item(item_id: str):
        """Get item by ID."""
        return {}

    app.include_router(router)
    return app
'''
    app_path = tmp_dir / "app.py"
    app_path.write_text(app_code)
    return app_path


class TestParseStrategyYaml:
    def test_parses_valid_yaml(self, strategies_dir):
        result = parse_strategy_yaml(strategies_dir / "test_strategy.yaml")
        assert result["name"] == "TEST_STRATEGY"
        assert len(result["indicators"]) == 2

    def test_returns_all_fields(self, strategies_dir):
        result = parse_strategy_yaml(strategies_dir / "test_strategy.yaml")
        assert "entryConditions" in result
        assert "exitConditions" in result
        assert "parameters" in result


class TestLoadAllStrategies:
    def test_loads_all_yaml_files(self, strategies_dir):
        strategies = load_all_strategies(strategies_dir)
        assert len(strategies) == 2

    def test_sorted_by_filename(self, strategies_dir):
        strategies = load_all_strategies(strategies_dir)
        names = [s["name"] for s in strategies]
        assert names == ["RSI_STRATEGY", "TEST_STRATEGY"]

    def test_adds_file_metadata(self, strategies_dir):
        strategies = load_all_strategies(strategies_dir)
        assert all("_file" in s for s in strategies)


class TestGenerateStrategyReference:
    def test_contains_header(self, sample_strategy):
        doc = generate_strategy_reference([sample_strategy])
        assert "# Strategy Reference" in doc

    def test_contains_strategy_count(self, sample_strategy):
        doc = generate_strategy_reference([sample_strategy])
        assert "Total strategies: 1" in doc

    def test_contains_strategy_name(self, sample_strategy):
        doc = generate_strategy_reference([sample_strategy])
        assert "TEST_STRATEGY" in doc

    def test_contains_overview_table(self, sample_strategy):
        doc = generate_strategy_reference([sample_strategy])
        assert "| Strategy |" in doc

    def test_contains_parameters_table(self, sample_strategy):
        doc = generate_strategy_reference([sample_strategy])
        assert "smaPeriod" in doc
        assert "emaPeriod" in doc

    def test_contains_entry_exit_conditions(self, sample_strategy):
        doc = generate_strategy_reference([sample_strategy])
        assert "CROSSED_UP" in doc
        assert "CROSSED_DOWN" in doc

    def test_empty_strategies_list(self):
        doc = generate_strategy_reference([])
        assert "Total strategies: 0" in doc


class TestExtractIndicators:
    def test_extracts_unique_types(self, sample_strategy):
        indicators = extract_indicators([sample_strategy])
        assert "SMA" in indicators
        assert "EMA" in indicators

    def test_tracks_strategy_usage(self, sample_strategy):
        indicators = extract_indicators([sample_strategy])
        assert "TEST_STRATEGY" in indicators["SMA"]["strategies"]

    def test_tracks_params(self, sample_strategy):
        indicators = extract_indicators([sample_strategy])
        assert "period" in indicators["SMA"]["params_seen"]


class TestGenerateIndicatorReference:
    def test_contains_header(self, sample_strategy):
        doc = generate_indicator_reference([sample_strategy])
        assert "# Indicator Reference" in doc

    def test_lists_indicator_types(self, sample_strategy):
        doc = generate_indicator_reference([sample_strategy])
        assert "SMA" in doc
        assert "EMA" in doc

    def test_shows_usage_count(self):
        strategies = [
            {
                "name": "S1",
                "indicators": [{"id": "sma", "type": "SMA", "params": {}}],
            },
            {
                "name": "S2",
                "indicators": [{"id": "sma2", "type": "SMA", "params": {}}],
            },
        ]
        doc = generate_indicator_reference(strategies)
        assert "2" in doc  # SMA used in 2 strategies


class TestParseFastapiRoutes:
    def test_parses_routes(self, fastapi_app_file):
        routes = parse_fastapi_routes(fastapi_app_file)
        assert len(routes) == 3

    def test_extracts_methods(self, fastapi_app_file):
        routes = parse_fastapi_routes(fastapi_app_file)
        methods = {r["method"] for r in routes}
        assert "GET" in methods
        assert "POST" in methods

    def test_extracts_paths(self, fastapi_app_file):
        routes = parse_fastapi_routes(fastapi_app_file)
        paths = {r["path"] for r in routes}
        assert "/api/v1/test/items" in paths
        assert "/api/v1/test/items/{item_id}" in paths

    def test_extracts_docstrings(self, fastapi_app_file):
        routes = parse_fastapi_routes(fastapi_app_file)
        docstrings = {r["function"]: r["docstring"] for r in routes}
        assert docstrings["list_items"] == "List all items."

    def test_handles_nonexistent_file(self, tmp_dir):
        routes = parse_fastapi_routes(tmp_dir / "nonexistent.py")
        assert routes == []


class TestGenerateApiReference:
    def test_generates_output(self, tmp_dir, fastapi_app_file):
        # Set up a service directory structure
        svc_dir = tmp_dir / "services"
        svc_dir.mkdir()
        test_svc = svc_dir / "test_api"
        test_svc.mkdir()
        (test_svc / "app.py").write_text(fastapi_app_file.read_text())

        doc = generate_api_reference(svc_dir)
        assert "# API Reference" in doc
        assert "Test Api" in doc

    def test_no_services(self, tmp_dir):
        svc_dir = tmp_dir / "services"
        svc_dir.mkdir()
        doc = generate_api_reference(svc_dir)
        assert "No FastAPI services found." in doc


class TestGenerateServiceGraph:
    def test_generates_mermaid(self, tmp_dir):
        svc_dir = tmp_dir / "services"
        svc_dir.mkdir()
        svc = svc_dir / "test_service"
        svc.mkdir()
        (svc / "main.py").write_text('import asyncpg\nPOSTGRES_URL = "test"')

        doc = generate_service_graph(svc_dir)
        assert "```mermaid" in doc
        assert "graph TB" in doc

    def test_detects_postgres(self, tmp_dir):
        svc_dir = tmp_dir / "services"
        svc_dir.mkdir()
        svc = svc_dir / "db_service"
        svc.mkdir()
        (svc / "main.py").write_text('import asyncpg\nconn = asyncpg.connect()')

        doc = generate_service_graph(svc_dir)
        assert "POSTGRES" in doc


class TestGenerateAll:
    def test_generates_all_files(self, tmp_dir):
        # Set up a minimal repo structure
        repo = tmp_dir / "repo"
        repo.mkdir()
        (repo / "MODULE.bazel").write_text("")

        strat_dir = repo / "src" / "main" / "resources" / "strategies"
        strat_dir.mkdir(parents=True)
        with open(strat_dir / "test.yaml", "w") as f:
            yaml.dump(
                {
                    "name": "TEST",
                    "description": "Test",
                    "indicators": [],
                    "parameters": [],
                },
                f,
            )

        svc_dir = repo / "services"
        svc_dir.mkdir()

        output = tmp_dir / "output"
        generated = generate_all(repo, output)

        assert len(generated) == 5
        assert (output / "strategy-reference.md").exists()
        assert (output / "indicator-reference.md").exists()
        assert (output / "api-reference.md").exists()
        assert (output / "service-architecture.md").exists()
        assert (output / "index.md").exists()

    def test_index_contains_links(self, tmp_dir):
        repo = tmp_dir / "repo"
        repo.mkdir()
        (repo / "MODULE.bazel").write_text("")
        strat_dir = repo / "src" / "main" / "resources" / "strategies"
        strat_dir.mkdir(parents=True)
        svc_dir = repo / "services"
        svc_dir.mkdir()

        output = tmp_dir / "output"
        generate_all(repo, output)

        index = (output / "index.md").read_text()
        assert "strategy-reference.md" in index
        assert "api-reference.md" in index
        assert "service-architecture.md" in index
