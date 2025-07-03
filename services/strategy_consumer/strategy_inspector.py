#!/usr/bin/env python3
"""
Strategy Inspector - A utility to inspect strategies stored in the database.

Usage:
    bazel run //services/strategy_consumer:strategy_inspector -- --symbol BTC/USD --limit 10
    bazel run //services/strategy_consumer:strategy_inspector -- --symbol ETH/USD --limit 5 --min-score 0.8
"""

import argparse
import json
import sys
from typing import List, Optional

import asyncpg
from google.protobuf import any_pb2

# Import the generated protobuf classes
from protos import strategies_pb2


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
    
    def decode_protobuf_parameters(self, protobuf_data: str, protobuf_type: str) -> dict:
        """Decode protobuf parameters to a readable format."""
        try:
            # Map protobuf types to their corresponding classes
            type_mapping = {
                "type.googleapis.com/strategies.SmaRsiParameters": strategies_pb2.SmaRsiParameters,
                "type.googleapis.com/strategies.EmaMacdParameters": strategies_pb2.EmaMacdParameters,
                "type.googleapis.com/strategies.AdxStochasticParameters": strategies_pb2.AdxStochasticParameters,
                "type.googleapis.com/strategies.AroonMfiParameters": strategies_pb2.AroonMfiParameters,
                "type.googleapis.com/strategies.IchimokuCloudParameters": strategies_pb2.IchimokuCloudParameters,
                "type.googleapis.com/strategies.ParabolicSarParameters": strategies_pb2.ParabolicSarParameters,
                "type.googleapis.com/strategies.SmaEmaCrossoverParameters": strategies_pb2.SmaEmaCrossoverParameters,
                "type.googleapis.com/strategies.DoubleEmaCrossoverParameters": strategies_pb2.DoubleEmaCrossoverParameters,
                "type.googleapis.com/strategies.TripleEmaCrossoverParameters": strategies_pb2.TripleEmaCrossoverParameters,
                "type.googleapis.com/strategies.HeikenAshiParameters": strategies_pb2.HeikenAshiParameters,
                "type.googleapis.com/strategies.LinearRegressionChannelsParameters": strategies_pb2.LinearRegressionChannelsParameters,
                "type.googleapis.com/strategies.VwapMeanReversionParameters": strategies_pb2.VwapMeanReversionParameters,
                "type.googleapis.com/strategies.BbandWRParameters": strategies_pb2.BbandWRParameters,
                "type.googleapis.com/strategies.AtrCciParameters": strategies_pb2.AtrCciParameters,
                "type.googleapis.com/strategies.DonchianBreakoutParameters": strategies_pb2.DonchianBreakoutParameters,
                "type.googleapis.com/strategies.VolatilityStopParameters": strategies_pb2.VolatilityStopParameters,
                "type.googleapis.com/strategies.AtrTrailingStopParameters": strategies_pb2.AtrTrailingStopParameters,
                "type.googleapis.com/strategies.MomentumSmaCrossoverParameters": strategies_pb2.MomentumSmaCrossoverParameters,
                "type.googleapis.com/strategies.KstOscillatorParameters": strategies_pb2.KstOscillatorParameters,
                "type.googleapis.com/strategies.StochasticRsiParameters": strategies_pb2.StochasticRsiParameters,
                "type.googleapis.com/strategies.RviParameters": strategies_pb2.RviParameters,
                "type.googleapis.com/strategies.MassIndexParameters": strategies_pb2.MassIndexParameters,
                "type.googleapis.com/strategies.MomentumPinballParameters": strategies_pb2.MomentumPinballParameters,
                "type.googleapis.com/strategies.VolumeWeightedMacdParameters": strategies_pb2.VolumeWeightedMacdParameters,
                "type.googleapis.com/strategies.ObvEmaParameters": strategies_pb2.ObvEmaParameters,
                "type.googleapis.com/strategies.ChaikinOscillatorParameters": strategies_pb2.ChaikinOscillatorParameters,
                "type.googleapis.com/strategies.KlingerVolumeParameters": strategies_pb2.KlingerVolumeParameters,
                "type.googleapis.com/strategies.VolumeBreakoutParameters": strategies_pb2.VolumeBreakoutParameters,
                "type.googleapis.com/strategies.PvtParameters": strategies_pb2.PvtParameters,
                "type.googleapis.com/strategies.VptParameters": strategies_pb2.VptParameters,
                "type.googleapis.com/strategies.VolumeSpreadAnalysisParameters": strategies_pb2.VolumeSpreadAnalysisParameters,
                "type.googleapis.com/strategies.TickVolumeAnalysisParameters": strategies_pb2.TickVolumeAnalysisParameters,
                "type.googleapis.com/strategies.VolumeProfileDeviationsParameters": strategies_pb2.VolumeProfileDeviationsParameters,
                "type.googleapis.com/strategies.VolumeProfileParameters": strategies_pb2.VolumeProfileParameters,
                "type.googleapis.com/strategies.StochasticEmaParameters": strategies_pb2.StochasticEmaParameters,
                "type.googleapis.com/strategies.CmoMfiParameters": strategies_pb2.CmoMfiParameters,
                "type.googleapis.com/strategies.RsiEmaCrossoverParameters": strategies_pb2.RsiEmaCrossoverParameters,
                "type.googleapis.com/strategies.TrixSignalLineParameters": strategies_pb2.TrixSignalLineParameters,
                "type.googleapis.com/strategies.CmfZeroLineParameters": strategies_pb2.CmfZeroLineParameters,
                "type.googleapis.com/strategies.RainbowOscillatorParameters": strategies_pb2.RainbowOscillatorParameters,
                "type.googleapis.com/strategies.PriceOscillatorSignalParameters": strategies_pb2.PriceOscillatorSignalParameters,
                "type.googleapis.com/strategies.AwesomeOscillatorParameters": strategies_pb2.AwesomeOscillatorParameters,
                "type.googleapis.com/strategies.DemaTemaCrossoverParameters": strategies_pb2.DemaTemaCrossoverParameters,
                "type.googleapis.com/strategies.MacdCrossoverParameters": strategies_pb2.MacdCrossoverParameters,
                "type.googleapis.com/strategies.VwapCrossoverParameters": strategies_pb2.VwapCrossoverParameters,
                "type.googleapis.com/strategies.RocMaCrossoverParameters": strategies_pb2.RocMaCrossoverParameters,
                "type.googleapis.com/strategies.RegressionChannelParameters": strategies_pb2.RegressionChannelParameters,
                "type.googleapis.com/strategies.FramaParameters": strategies_pb2.FramaParameters,
                "type.googleapis.com/strategies.PivotParameters": strategies_pb2.PivotParameters,
                "type.googleapis.com/strategies.DoubleTopBottomParameters": strategies_pb2.DoubleTopBottomParameters,
                "type.googleapis.com/strategies.FibonacciRetracementsParameters": strategies_pb2.FibonacciRetracementsParameters,
                "type.googleapis.com/strategies.PriceGapParameters": strategies_pb2.PriceGapParameters,
                "type.googleapis.com/strategies.RenkoChartParameters": strategies_pb2.RenkoChartParameters,
                "type.googleapis.com/strategies.RangeBarsParameters": strategies_pb2.RangeBarsParameters,
                "type.googleapis.com/strategies.GannSwingParameters": strategies_pb2.GannSwingParameters,
                "type.googleapis.com/strategies.SarMfiParameters": strategies_pb2.SarMfiParameters,
                "type.googleapis.com/strategies.AdxDmiParameters": strategies_pb2.AdxDmiParameters,
                "type.googleapis.com/strategies.ElderRayMAParameters": strategies_pb2.ElderRayMAParameters,
                "type.googleapis.com/strategies.DpoCrossoverParameters": strategies_pb2.DpoCrossoverParameters,
                "type.googleapis.com/strategies.VariablePeriodEmaParameters": strategies_pb2.VariablePeriodEmaParameters,
            }
            if protobuf_type in type_mapping:
                param_class = type_mapping[protobuf_type]()
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
            else:
                return {"error": f"Unknown protobuf type: {protobuf_type}"}
        except Exception as e:
            return {"error": f"Failed to decode protobuf: {str(e)}"}
    
    async def get_strategies(self, symbol: str, limit: int = 10, min_score: Optional[float] = None) -> List[dict]:
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
                params_field = strategy['parameters']
                if isinstance(params_field, str):
                    try:
                        params_field = json.loads(params_field)
                    except Exception:
                        params_field = None
                
                # Decode the parameters
                if params_field and isinstance(params_field, dict) and 'protobuf_data' in params_field:
                    decoded_params = self.decode_protobuf_parameters(
                        params_field['protobuf_data'],
                        params_field['protobuf_type']
                    )
                    strategy['decoded_parameters'] = decoded_params
                
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
            
            if show_parameters and 'decoded_parameters' in strategy:
                print(f"   Parameters:")
                for key, value in strategy['decoded_parameters'].items():
                    print(f"     {key}: {value}")
            
            print("-" * 40)


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Inspect strategies from the database")
    parser.add_argument("--symbol", default="BTC/USD", help="Symbol to query (default: BTC/USD)")
    parser.add_argument("--limit", type=int, default=10, help="Number of strategies to retrieve (default: 10)")
    parser.add_argument("--min-score", type=float, help="Minimum score threshold")
    parser.add_argument("--host", default="localhost", help="Database host (default: localhost)")
    parser.add_argument("--port", type=int, default=5432, help="Database port (default: 5432)")
    parser.add_argument("--database", default="tradestream", help="Database name (default: tradestream)")
    parser.add_argument("--username", default="postgres", help="Database username (default: postgres)")
    parser.add_argument("--password", default="tradestream123", help="Database password (default: tradestream123)")
    parser.add_argument("--no-parameters", action="store_true", help="Hide parameter details")
    
    args = parser.parse_args()
    
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
            symbol=args.symbol,
            limit=args.limit,
            min_score=args.min_score
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