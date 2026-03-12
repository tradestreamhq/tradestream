#!/usr/bin/env python3
"""
TradeStream Documentation Generator.

Auto-generates API docs, strategy reference, indicator reference,
and service dependency graph from code and YAML configs.
"""

import argparse
import ast
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


def find_repo_root() -> Path:
    """Find the repository root by looking for MODULE.bazel."""
    path = Path(__file__).resolve()
    for parent in [path] + list(path.parents):
        if (parent / "MODULE.bazel").exists():
            return parent
    raise FileNotFoundError("Could not find repository root (MODULE.bazel)")


# ---------------------------------------------------------------------------
# Strategy reference
# ---------------------------------------------------------------------------


def parse_strategy_yaml(path: Path) -> Dict[str, Any]:
    """Parse a single strategy YAML config."""
    with open(path) as f:
        return yaml.safe_load(f)


def load_all_strategies(strategies_dir: Path) -> List[Dict[str, Any]]:
    """Load and return all strategy configs sorted by name."""
    strategies = []
    for yaml_file in sorted(strategies_dir.glob("*.yaml")):
        try:
            data = parse_strategy_yaml(yaml_file)
            if data and "name" in data:
                data["_file"] = yaml_file.name
                strategies.append(data)
        except Exception as e:
            print(f"Warning: failed to parse {yaml_file}: {e}", file=sys.stderr)
    return strategies


def generate_strategy_reference(strategies: List[Dict[str, Any]]) -> str:
    """Generate Markdown strategy reference documentation."""
    lines = [
        "# Strategy Reference",
        "",
        "Auto-generated from YAML configs in `src/main/resources/strategies/`.",
        "",
        f"**Total strategies: {len(strategies)}**",
        "",
        "## Overview",
        "",
        "| Strategy | Complexity | Indicators | Description |",
        "|----------|-----------|------------|-------------|",
    ]

    for s in strategies:
        indicators = ", ".join(i.get("type", "?") for i in s.get("indicators", []))
        complexity = s.get("complexity", "N/A")
        desc = s.get("description", "").replace("|", "\\|")
        lines.append(f"| {s['name']} | {complexity} | {indicators} | {desc} |")

    lines.append("")
    lines.append("## Strategy Details")
    lines.append("")

    for s in strategies:
        lines.append(f"### {s['name']}")
        lines.append("")
        lines.append(f"**File:** `{s.get('_file', 'N/A')}`  ")
        lines.append(f"**Complexity:** {s.get('complexity', 'N/A')}  ")
        lines.append(
            f"**Description:** {s.get('description', 'No description provided')}"
        )
        lines.append("")

        # Indicators
        indicators = s.get("indicators", [])
        if indicators:
            lines.append("#### Indicators")
            lines.append("")
            lines.append("| ID | Type | Input | Parameters |")
            lines.append("|----|------|-------|------------|")
            for ind in indicators:
                params = ind.get("params", {})
                param_str = ", ".join(
                    f"{k}={v}" for k, v in sorted(params.items())
                )
                lines.append(
                    f"| {ind.get('id', 'N/A')} | {ind.get('type', 'N/A')} "
                    f"| {ind.get('input', 'N/A')} | {param_str} |"
                )
            lines.append("")

        # Entry conditions
        entry = s.get("entryConditions", [])
        if entry:
            lines.append("#### Entry Conditions")
            lines.append("")
            for cond in entry:
                params = cond.get("params", {})
                param_str = ", ".join(
                    f"{k}={v}" for k, v in sorted(params.items())
                )
                lines.append(
                    f"- **{cond.get('type', '?')}** on `{cond.get('indicator', '?')}`"
                    + (f" ({param_str})" if param_str else "")
                )
            lines.append("")

        # Exit conditions
        exit_conds = s.get("exitConditions", [])
        if exit_conds:
            lines.append("#### Exit Conditions")
            lines.append("")
            for cond in exit_conds:
                params = cond.get("params", {})
                param_str = ", ".join(
                    f"{k}={v}" for k, v in sorted(params.items())
                )
                lines.append(
                    f"- **{cond.get('type', '?')}** on `{cond.get('indicator', '?')}`"
                    + (f" ({param_str})" if param_str else "")
                )
            lines.append("")

        # Parameters
        parameters = s.get("parameters", [])
        if parameters:
            lines.append("#### Parameters")
            lines.append("")
            lines.append("| Name | Type | Min | Max | Default |")
            lines.append("|------|------|-----|-----|---------|")
            for p in parameters:
                lines.append(
                    f"| {p.get('name', '?')} | {p.get('type', '?')} "
                    f"| {p.get('min', 'N/A')} | {p.get('max', 'N/A')} "
                    f"| {p.get('defaultValue', 'N/A')} |"
                )
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Indicator reference
# ---------------------------------------------------------------------------


def extract_indicators(strategies: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Extract unique indicator types and their usage across strategies."""
    indicators: Dict[str, Dict[str, Any]] = {}
    for s in strategies:
        for ind in s.get("indicators", []):
            ind_type = ind.get("type", "UNKNOWN")
            if ind_type not in indicators:
                indicators[ind_type] = {
                    "type": ind_type,
                    "strategies": [],
                    "params_seen": set(),
                }
            indicators[ind_type]["strategies"].append(s["name"])
            for k in ind.get("params", {}):
                indicators[ind_type]["params_seen"].add(k)
    return indicators


def generate_indicator_reference(strategies: List[Dict[str, Any]]) -> str:
    """Generate indicator reference documentation."""
    indicators = extract_indicators(strategies)

    lines = [
        "# Indicator Reference",
        "",
        "Auto-generated from strategy YAML configs.",
        "",
        f"**Total unique indicator types: {len(indicators)}**",
        "",
        "| Indicator | Used In # Strategies | Parameters |",
        "|-----------|---------------------|------------|",
    ]

    for name in sorted(indicators):
        info = indicators[name]
        count = len(info["strategies"])
        params = ", ".join(sorted(info["params_seen"])) or "none"
        lines.append(f"| {name} | {count} | {params} |")

    lines.append("")
    lines.append("## Details")
    lines.append("")

    for name in sorted(indicators):
        info = indicators[name]
        lines.append(f"### {name}")
        lines.append("")
        lines.append(f"Used in **{len(info['strategies'])}** strategies:")
        lines.append("")
        for s_name in sorted(set(info["strategies"])):
            lines.append(f"- {s_name}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# API reference (FastAPI parsing)
# ---------------------------------------------------------------------------


def parse_fastapi_routes(app_path: Path) -> List[Dict[str, str]]:
    """Parse FastAPI route definitions from an app.py file using AST."""
    try:
        source = app_path.read_text()
    except Exception:
        return []

    routes: List[Dict[str, str]] = []

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    # Extract root_path from FastAPI() constructor
    root_path = ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "FastAPI":
                for kw in node.keywords:
                    if kw.arg == "root_path" and isinstance(kw.value, ast.Constant):
                        root_path = kw.value.value
            elif isinstance(func, ast.Attribute) and func.attr == "FastAPI":
                for kw in node.keywords:
                    if kw.arg == "root_path" and isinstance(kw.value, ast.Constant):
                        root_path = kw.value.value

    # Find APIRouter prefix definitions
    router_prefixes: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func = node.value.func
            if (isinstance(func, ast.Name) and func.id == "APIRouter") or (
                isinstance(func, ast.Attribute) and func.attr == "APIRouter"
            ):
                prefix = ""
                for kw in node.value.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                        prefix = kw.value.value
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        router_prefixes[target.id] = prefix

    # Find route decorators
    http_methods = {"get", "post", "put", "delete", "patch"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and isinstance(
                    decorator.func, ast.Attribute
                ):
                    method = decorator.func.attr
                    if method not in http_methods:
                        continue

                    # Get router name
                    router_name = ""
                    if isinstance(decorator.func.value, ast.Name):
                        router_name = decorator.func.value.id

                    # Get path from first positional arg
                    path = ""
                    if decorator.args and isinstance(
                        decorator.args[0], ast.Constant
                    ):
                        path = decorator.args[0].value

                    # Build full path
                    prefix = router_prefixes.get(router_name, "")
                    full_path = root_path + prefix + path

                    # Extract docstring
                    docstring = ast.get_docstring(node) or ""

                    routes.append(
                        {
                            "method": method.upper(),
                            "path": full_path,
                            "function": node.name,
                            "docstring": docstring,
                        }
                    )

    return routes


def discover_api_services(services_dir: Path) -> List[Tuple[str, Path]]:
    """Find services with FastAPI app.py files."""
    results = []
    for svc_dir in sorted(services_dir.iterdir()):
        if not svc_dir.is_dir():
            continue
        app_py = svc_dir / "app.py"
        if app_py.exists():
            # Check if it's a FastAPI app
            content = app_py.read_text()
            if "FastAPI" in content:
                results.append((svc_dir.name, app_py))
    return results


def generate_api_reference(services_dir: Path) -> str:
    """Generate API reference documentation from FastAPI services."""
    api_services = discover_api_services(services_dir)

    lines = [
        "# API Reference",
        "",
        "Auto-generated from FastAPI service definitions.",
        "",
    ]

    if not api_services:
        lines.append("No FastAPI services found.")
        return "\n".join(lines)

    lines.append(f"**{len(api_services)} API services detected.**")
    lines.append("")

    for svc_name, app_path in api_services:
        routes = parse_fastapi_routes(app_path)
        title = svc_name.replace("_", " ").title()

        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"**Source:** `services/{svc_name}/app.py`")
        lines.append("")

        if not routes:
            lines.append("_No routes parsed._")
            lines.append("")
            continue

        lines.append("| Method | Path | Description |")
        lines.append("|--------|------|-------------|")
        for r in routes:
            desc = r["docstring"].split("\n")[0] if r["docstring"] else r["function"]
            desc = desc.replace("|", "\\|")
            lines.append(f"| `{r['method']}` | `{r['path']}` | {desc} |")

        lines.append("")

        # Detailed endpoint docs
        for r in routes:
            lines.append(f"### `{r['method']} {r['path']}`")
            lines.append("")
            lines.append(f"**Handler:** `{r['function']}`")
            lines.append("")
            if r["docstring"]:
                lines.append(r["docstring"])
                lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Service dependency graph
# ---------------------------------------------------------------------------

# Maps service names to categories
SERVICE_CATEGORIES = {
    "candle_ingestor": "Data Ingestion",
    "top_crypto_updater": "Data Ingestion",
    "polymarket_ingestor": "Data Ingestion",
    "strategy_discovery_request_factory": "Strategy Discovery",
    "strategy_consumer": "Strategy Discovery",
    "strategy_confidence_scorer": "Strategy Discovery",
    "strategy_rotation": "Strategy Management",
    "strategy_ensemble": "Strategy Management",
    "strategy_time_filter": "Strategy Management",
    "risk_adjusted_sizing": "Portfolio & Risk",
    "portfolio_state": "Portfolio & Risk",
    "portfolio_api": "Portfolio & Risk",
    "signal_generator_agent": "AI Agents",
    "strategy_proposer_agent": "AI Agents",
    "opportunity_scorer_agent": "AI Agents",
    "orchestrator_agent": "AI Agents",
    "learning_engine": "AI Agents",
    "agent_gateway": "AI Agents",
    "backtesting": "Evaluation",
    "paper_trading": "Evaluation",
    "strategy_api": "REST APIs",
    "market_data_api": "REST APIs",
    "learning_api": "REST APIs",
    "strategy_monitor_api": "REST APIs",
    "strategy_mcp": "MCP Servers",
    "market_mcp": "MCP Servers",
    "signal_mcp": "MCP Servers",
    "signal_dashboard": "Delivery",
    "notification_service": "Delivery",
    "wallet_anomaly_detector": "Monitoring",
}


def detect_service_deps(services_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Detect service dependencies from imports and infrastructure usage."""
    services: Dict[str, Dict[str, Any]] = {}

    for svc_dir in sorted(services_dir.iterdir()):
        if not svc_dir.is_dir() or svc_dir.name in ("shared", "rest_api_shared", "__pycache__"):
            continue

        svc_name = svc_dir.name
        deps: Dict[str, List[str]] = {
            "kafka": [],
            "postgres": [],
            "redis": [],
            "influxdb": [],
            "services": [],
        }

        # Scan all Python files in the service
        for py_file in svc_dir.glob("*.py"):
            try:
                content = py_file.read_text()
            except Exception:
                continue

            # Kafka
            if "KafkaConsumer" in content or "consumer" in content.lower():
                for m in re.findall(r'["\']([a-z][a-z0-9-]+(?:-[a-z0-9]+)*)["\']', content):
                    if any(
                        kw in m
                        for kw in (
                            "strategy",
                            "signal",
                            "candle",
                            "position",
                            "risk",
                            "discovery",
                        )
                    ):
                        if m not in deps["kafka"]:
                            deps["kafka"].append(m)
            if "KafkaProducer" in content or "producer" in content.lower():
                for m in re.findall(r'["\']([a-z][a-z0-9-]+(?:-[a-z0-9]+)*)["\']', content):
                    if any(
                        kw in m
                        for kw in (
                            "strategy",
                            "signal",
                            "candle",
                            "position",
                            "risk",
                            "discovery",
                        )
                    ):
                        if m not in deps["kafka"]:
                            deps["kafka"].append(m)

            # Database
            if "asyncpg" in content or "psycopg" in content or "POSTGRES" in content:
                deps["postgres"] = ["yes"]
            if "redis" in content.lower() or "REDIS" in content:
                deps["redis"] = ["yes"]
            if "influx" in content.lower() or "INFLUX" in content:
                deps["influxdb"] = ["yes"]

            # Cross-service imports
            for m in re.findall(r"from services\.(\w+)", content):
                if m != svc_name and m not in ("shared", "rest_api_shared"):
                    if m not in deps["services"]:
                        deps["services"].append(m)

        category = SERVICE_CATEGORIES.get(svc_name, "Other")
        services[svc_name] = {"deps": deps, "category": category}

    return services


def generate_service_graph(services_dir: Path) -> str:
    """Generate service dependency graph documentation with Mermaid diagram."""
    services = detect_service_deps(services_dir)

    lines = [
        "# Service Architecture",
        "",
        "Auto-generated from service source code.",
        "",
        f"**Total services: {len(services)}**",
        "",
        "## Service Dependency Graph",
        "",
        "```mermaid",
        "graph TB",
    ]

    # Group by category
    categories: Dict[str, List[str]] = {}
    for svc_name, info in services.items():
        cat = info["category"]
        categories.setdefault(cat, []).append(svc_name)

    for cat, svc_list in sorted(categories.items()):
        safe_cat = cat.replace(" ", "_").replace("&", "and")
        lines.append(f'    subgraph "{cat}"')
        for svc in sorted(svc_list):
            label = svc.replace("_", " ").title()
            lines.append(f"        {svc}[{label}]")
        lines.append("    end")

    # Infrastructure nodes
    lines.append('    subgraph "Infrastructure"')
    lines.append("        KAFKA[(Kafka)]")
    lines.append("        POSTGRES[(PostgreSQL)]")
    lines.append("        REDIS[(Redis)]")
    lines.append("        INFLUXDB[(InfluxDB)]")
    lines.append("    end")

    # Edges
    for svc_name, info in sorted(services.items()):
        deps = info["deps"]
        if deps["kafka"]:
            lines.append(f"    {svc_name} --> KAFKA")
        if deps["postgres"]:
            lines.append(f"    {svc_name} --> POSTGRES")
        if deps["redis"]:
            lines.append(f"    {svc_name} --> REDIS")
        if deps["influxdb"]:
            lines.append(f"    {svc_name} --> INFLUXDB")
        for dep_svc in deps["services"]:
            if dep_svc in services:
                lines.append(f"    {svc_name} -.-> {dep_svc}")

    lines.append("```")
    lines.append("")

    # Service table
    lines.append("## Service Inventory")
    lines.append("")
    lines.append("| Service | Category | Kafka | PostgreSQL | Redis | InfluxDB |")
    lines.append("|---------|----------|-------|-----------|-------|----------|")

    for svc_name in sorted(services):
        info = services[svc_name]
        deps = info["deps"]
        kafka = "Y" if deps["kafka"] else ""
        pg = "Y" if deps["postgres"] else ""
        redis = "Y" if deps["redis"] else ""
        influx = "Y" if deps["influxdb"] else ""
        lines.append(
            f"| {svc_name} | {info['category']} | {kafka} | {pg} | {redis} | {influx} |"
        )

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def generate_all(repo_root: Path, output_dir: Path) -> List[str]:
    """Generate all documentation files. Returns list of generated file paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = []

    strategies_dir = repo_root / "src" / "main" / "resources" / "strategies"
    services_dir = repo_root / "services"

    # Strategy reference
    strategies = load_all_strategies(strategies_dir)
    strategy_doc = generate_strategy_reference(strategies)
    strategy_path = output_dir / "strategy-reference.md"
    strategy_path.write_text(strategy_doc)
    generated.append(str(strategy_path))

    # Indicator reference
    indicator_doc = generate_indicator_reference(strategies)
    indicator_path = output_dir / "indicator-reference.md"
    indicator_path.write_text(indicator_doc)
    generated.append(str(indicator_path))

    # API reference
    api_doc = generate_api_reference(services_dir)
    api_path = output_dir / "api-reference.md"
    api_path.write_text(api_doc)
    generated.append(str(api_path))

    # Service architecture
    arch_doc = generate_service_graph(services_dir)
    arch_path = output_dir / "service-architecture.md"
    arch_path.write_text(arch_doc)
    generated.append(str(arch_path))

    # Index page
    index_doc = generate_index(strategies, services_dir)
    index_path = output_dir / "index.md"
    index_path.write_text(index_doc)
    generated.append(str(index_path))

    return generated


def generate_index(
    strategies: List[Dict[str, Any]], services_dir: Path
) -> str:
    """Generate docs index page."""
    api_count = len(discover_api_services(services_dir))
    indicators = extract_indicators(strategies)
    services = detect_service_deps(services_dir)

    return "\n".join(
        [
            "# TradeStream Documentation",
            "",
            "Auto-generated documentation for the TradeStream algorithmic trading platform.",
            "",
            "## Contents",
            "",
            f"- [Strategy Reference](strategy-reference.md) — {len(strategies)} strategies",
            f"- [Indicator Reference](indicator-reference.md) — {len(indicators)} indicator types",
            f"- [API Reference](api-reference.md) — {api_count} API services",
            f"- [Service Architecture](service-architecture.md) — {len(services)} microservices",
            "",
            "## Regenerating",
            "",
            "```bash",
            "python -m tools.docgen.generate",
            "```",
            "",
            "Documentation is verified in CI — if code or configs change,",
            "regenerate docs and commit the result.",
            "",
        ]
    )


def main():
    parser = argparse.ArgumentParser(description="Generate TradeStream documentation")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (auto-detected if omitted)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (defaults to <repo>/docs/generated)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if generated docs are up to date (exit 1 if not)",
    )
    args = parser.parse_args()

    repo_root = args.repo_root or find_repo_root()
    output_dir = args.output_dir or (repo_root / "docs" / "generated")

    if args.check:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            generate_all(repo_root, tmp_path)

            # Compare each generated file
            stale = []
            for tmp_file in sorted(tmp_path.iterdir()):
                existing = output_dir / tmp_file.name
                if not existing.exists():
                    stale.append(f"missing: {tmp_file.name}")
                elif existing.read_text() != tmp_file.read_text():
                    stale.append(f"outdated: {tmp_file.name}")

            if stale:
                print("Documentation is out of date:")
                for s in stale:
                    print(f"  {s}")
                print(
                    "\nRun `python -m tools.docgen.generate` to regenerate."
                )
                sys.exit(1)
            else:
                print("Documentation is up to date.")
                sys.exit(0)

    generated = generate_all(repo_root, output_dir)
    print(f"Generated {len(generated)} documentation files:")
    for f in generated:
        print(f"  {f}")


if __name__ == "__main__":
    main()
