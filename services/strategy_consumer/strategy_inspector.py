#!/usr/bin/env python3
"""
Strategy Inspector - A utility to inspect strategies stored in the database.

Usage:
    bazel run //services/strategy_consumer:strategy_inspector -- --symbol BTC/USD --limit 10
    bazel run //services/strategy_consumer:strategy_inspector -- --symbol ETH/USD --limit 5 --min-score 0.8
"""

import argparse
import json
import os
import sys
from typing import List, Optional

import asyncpg

from services.shared.strategy_parameter_registry import get_parameter_class


class StrategyInspector:
    """Utility class to inspect strategies from the database."""

    def __init__(self, db_config: dict):
        self.db_config = db_config
        self.pool = None

    async def connect(self):
        """Connect to the database."""
        self.pool = await asyncpg.create_pool(**self.db_config)

    async def close(self):
        """Close the database connection."""
        if self.pool:
            await self.pool.close()

    def decode_protobuf_parameters(
        self, protobuf_data: str, protobuf_type: str
    ) -> dict:
        """Decode protobuf parameters to a readable format."""
        try:
            param_class_type = get_parameter_class(protobuf_type)
            if param_class_type is None:
                return {"error": f"Unknown protobuf type: {protobuf_type}"}

            param_class = param_class_type()
            param_class.ParseFromString(bytes.fromhex(protobuf_data))
            # Convert to dict for easy display
            result = {}
            for field in param_class.DESCRIPTOR.fields:
                value = getattr(param_class, field.name)
                if field.type == field.TYPE_ENUM:
                    result[field.name] = field.enum_type.values_by_number[value].name
                else:
                    result[field.name] = value
            return result
        except Exception as e:
            return {"error": f"Failed to decode protobuf: {str(e)}"}

    async def get_strategies(
        self, symbol: str, limit: int = 10, min_score: Optional[float] = None
    ) -> List[dict]:
        """Get strategies for a given symbol, sorted by score descending."""
        if min_score is not None:
            query = """
                SELECT 
                    strategy_id,
                    symbol,
                    strategy_type,
                    parameters,
                    current_score,
                    created_at,
                    last_evaluated_at,
                    is_active
                FROM strategies 
                WHERE symbol = $1 AND current_score >= $2
                ORDER BY current_score DESC LIMIT $3
            """
            params = [symbol, min_score, limit]
        else:
            query = """
                SELECT 
                    strategy_id,
                    symbol,
                    strategy_type,
                    parameters,
                    current_score,
                    created_at,
                    last_evaluated_at,
                    is_active
                FROM strategies 
                WHERE symbol = $1
                ORDER BY current_score DESC LIMIT $2
            """
            params = [symbol, limit]

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

            strategies = []
            for row in rows:
                strategy = dict(row)

                # Parse parameters if it's a string
                params_field = strategy["parameters"]
                if isinstance(params_field, str):
                    try:
                        params_field = json.loads(params_field)
                    except Exception:
                        params_field = None

                # Decode the parameters
                if (
                    params_field
                    and isinstance(params_field, dict)
                    and "protobuf_data" in params_field
                ):
                    decoded_params = self.decode_protobuf_parameters(
                        params_field["protobuf_data"], params_field["protobuf_type"]
                    )
                    strategy["decoded_parameters"] = decoded_params

                strategies.append(strategy)

            return strategies

    def print_strategies(self, strategies: List[dict], show_parameters: bool = True):
        """Print strategies in a formatted way."""
        if not strategies:
            print(f"No strategies found.")
            return

        print(f"\nFound {len(strategies)} strategies:")
        print("=" * 80)

        for i, strategy in enumerate(strategies, 1):
            print(f"\n{i}. Strategy ID: {strategy['strategy_id']}")
            print(f"   Symbol: {strategy['symbol']}")
            print(f"   Type: {strategy['strategy_type']}")
            print(f"   Score: {strategy['current_score']:.4f}")
            print(f"   Active: {strategy['is_active']}")
            print(f"   Created: {strategy['created_at']}")
            print(f"   Last Evaluated: {strategy['last_evaluated_at']}")

            if show_parameters and "decoded_parameters" in strategy:
                print(f"   Parameters:")
                for key, value in strategy["decoded_parameters"].items():
                    print(f"     {key}: {value}")

            print("-" * 40)


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Inspect strategies from the database")
    parser.add_argument(
        "--symbol", default="BTC/USD", help="Symbol to query (default: BTC/USD)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of strategies to retrieve (default: 10)",
    )
    parser.add_argument("--min-score", type=float, help="Minimum score threshold")
    parser.add_argument(
        "--host", default="localhost", help="Database host (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=5432, help="Database port (default: 5432)"
    )
    parser.add_argument(
        "--database",
        default=os.environ.get("POSTGRES_DATABASE", ""),
        help="Database name (from POSTGRES_DATABASE env var)",
    )
    parser.add_argument(
        "--username", default="postgres", help="Database username (default: postgres)"
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Database password (required)",
    )
    parser.add_argument(
        "--no-parameters", action="store_true", help="Hide parameter details"
    )

    args = parser.parse_args()

    if not args.password:
        parser.error("--password is required")

    # Database configuration
    db_config = {
        "host": args.host,
        "port": args.port,
        "database": args.database,
        "user": args.username,
        "password": args.password,
    }

    inspector = StrategyInspector(db_config)

    try:
        await inspector.connect()
        print(f"Querying strategies for {args.symbol}...")

        strategies = await inspector.get_strategies(
            symbol=args.symbol, limit=args.limit, min_score=args.min_score
        )

        inspector.print_strategies(strategies, show_parameters=not args.no_parameters)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await inspector.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
