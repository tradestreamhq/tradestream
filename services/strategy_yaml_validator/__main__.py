"""
CLI entry point for strategy YAML validation and migration scaffolding.

Usage:
    python -m services.strategy_yaml_validator validate <yaml_file>
    python -m services.strategy_yaml_validator scaffold <strategy_name> [--output <file>]
"""

import argparse
import sys

from services.strategy_yaml_validator.migrate import scaffold_strategy_yaml
from services.strategy_yaml_validator.validator import StrategyYamlValidator


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate a strategy YAML file."""
    validator = StrategyYamlValidator()
    result = validator.validate_file(args.yaml_file)

    if result.is_valid:
        print(f"✓ {args.yaml_file} is valid")
        return 0

    print(f"✗ {args.yaml_file} has {len(result.errors)} error(s):")
    for err in result.errors:
        print(f"  - {err}")
    return 1


def cmd_scaffold(args: argparse.Namespace) -> int:
    """Generate a YAML template from a strategy name."""
    content = scaffold_strategy_yaml(args.strategy_name)
    if args.output:
        with open(args.output, "w") as f:
            f.write(content)
        print(f"Wrote scaffold to {args.output}")
    else:
        print(content)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="strategy_yaml_validator",
        description="TradeStream Strategy YAML Validator and Migration Tool",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate subcommand
    validate_parser = subparsers.add_parser(
        "validate", help="Validate a strategy YAML file"
    )
    validate_parser.add_argument("yaml_file", help="Path to the YAML file to validate")

    # scaffold subcommand
    scaffold_parser = subparsers.add_parser(
        "scaffold", help="Generate a YAML template from a strategy name"
    )
    scaffold_parser.add_argument(
        "strategy_name", help="Strategy name (e.g. DoubleEmaCrossover)"
    )
    scaffold_parser.add_argument(
        "--output", "-o", help="Output file path (prints to stdout if omitted)"
    )

    args = parser.parse_args()

    if args.command == "validate":
        return cmd_validate(args)
    elif args.command == "scaffold":
        return cmd_scaffold(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
