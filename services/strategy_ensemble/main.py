#!/usr/bin/env python3
"""
Strategy Ensemble - Phase 3 Implementation

This service creates strategy ensembles that:
- Combine multiple strategies for better performance
- Diversify across different strategy types
- Weight strategies by confidence and performance
- Provide ensemble-level risk management
- Enable dynamic rebalancing

The goal is to create robust trading portfolios from individual strategies.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from absl import app, flags, logging
from dataclasses import dataclass
from collections import defaultdict

import asyncpg

FLAGS = flags.FLAGS

# Database Configuration
flags.DEFINE_string("postgres_host", "localhost", "PostgreSQL host")
flags.DEFINE_integer("postgres_port", 5432, "PostgreSQL port")
flags.DEFINE_string("postgres_database", "tradestream", "PostgreSQL database")
flags.DEFINE_string("postgres_username", "postgres", "PostgreSQL username")
flags.DEFINE_string("postgres_password", "tradestream123", "PostgreSQL password")

# Ensemble Configuration
flags.DEFINE_integer("max_strategies_per_ensemble", 5, "Maximum strategies per ensemble")
flags.DEFINE_integer("min_strategies_per_ensemble", 2, "Minimum strategies per ensemble")
flags.DEFINE_float("min_ensemble_score", 0.7, "Minimum ensemble score to consider")
flags.DEFINE_float("diversification_weight", 0.3, "Weight for strategy type diversification")
flags.DEFINE_float("performance_weight", 0.7, "Weight for individual strategy performance")
flags.DEFINE_boolean("require_diversification", True, "Require different strategy types in ensemble")

# Output Configuration
flags.DEFINE_string("output_topic", "strategy-ensembles", "Kafka topic for strategy ensembles")
flags.DEFINE_boolean("dry_run", False, "Run in dry-run mode (no Kafka output)")


@dataclass
class EnsembleStrategy:
    """Represents a strategy within an ensemble."""
    strategy_id: str
    symbol: str
    strategy_type: str
    current_score: float
    weight: float
    contribution: float


@dataclass
class StrategyEnsemble:
    """Represents a strategy ensemble."""
    ensemble_id: str
    symbol: str
    strategies: List[EnsembleStrategy]
    total_score: float
    diversification_score: float
    performance_score: float
    risk_score: float
    created_at: datetime


class StrategyEnsembleBuilder:
    """Builds strategy ensembles from individual strategies."""
    
    def __init__(self, db_config: dict):
        self.db_config = db_config
        self.pool = None
        
    async def connect(self):
        """Connect to PostgreSQL."""
        self.pool = await asyncpg.create_pool(**self.db_config)
        logging.info("Connected to PostgreSQL")
        
    async def close(self):
        """Close database connection."""
        if self.pool:
            await self.pool.close()
            logging.info("Database connection closed")
    
    async def get_candidate_strategies(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get candidate strategies for ensemble building."""
        query = """
        SELECT 
            strategy_id,
            symbol,
            strategy_type,
            current_score,
            created_at,
            discovery_start_time,
            discovery_end_time
        FROM strategies 
        WHERE is_active = TRUE
        AND current_score >= 0.6
        """
        
        if symbol:
            query += " AND symbol = $1"
            params = [symbol]
        else:
            params = []
            
        query += " ORDER BY current_score DESC"
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    def build_ensembles(self, strategies: List[Dict]) -> List[StrategyEnsemble]:
        """Build strategy ensembles from candidate strategies."""
        ensembles = []
        
        # Group strategies by symbol
        strategies_by_symbol = defaultdict(list)
        for strategy in strategies:
            strategies_by_symbol[strategy['symbol']].append(strategy)
        
        # Build ensembles for each symbol
        for symbol, symbol_strategies in strategies_by_symbol.items():
            symbol_ensembles = self._build_ensembles_for_symbol(symbol, symbol_strategies)
            ensembles.extend(symbol_ensembles)
        
        return ensembles
    
    def _build_ensembles_for_symbol(self, symbol: str, strategies: List[Dict]) -> List[StrategyEnsemble]:
        """Build ensembles for a specific symbol."""
        ensembles = []
        
        # Sort strategies by score
        strategies.sort(key=lambda x: x['current_score'], reverse=True)
        
        # Create ensembles with different combinations
        for ensemble_size in range(FLAGS.min_strategies_per_ensemble, 
                                 min(FLAGS.max_strategies_per_ensemble + 1, len(strategies) + 1)):
            
            # Get top strategies for this ensemble size
            top_strategies = strategies[:ensemble_size]
            
            # Check if we have enough different strategy types
            strategy_types = set(s['strategy_type'] for s in top_strategies)
            if FLAGS.require_diversification and len(strategy_types) < 2:
                continue
            
            # Calculate ensemble metrics
            ensemble_metrics = self._calculate_ensemble_metrics(top_strategies)
            
            if ensemble_metrics['total_score'] >= FLAGS.min_ensemble_score:
                # Create ensemble strategies with weights
                ensemble_strategies = []
                for i, strategy in enumerate(top_strategies):
                    weight = ensemble_metrics['weights'][i]
                    contribution = strategy['current_score'] * weight
                    
                    ensemble_strategies.append(EnsembleStrategy(
                        strategy_id=strategy['strategy_id'],
                        symbol=strategy['symbol'],
                        strategy_type=strategy['strategy_type'],
                        current_score=strategy['current_score'],
                        weight=weight,
                        contribution=contribution
                    ))
                
                # Create ensemble
                ensemble = StrategyEnsemble(
                    ensemble_id=f"ensemble_{symbol}_{len(ensembles)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    symbol=symbol,
                    strategies=ensemble_strategies,
                    total_score=ensemble_metrics['total_score'],
                    diversification_score=ensemble_metrics['diversification_score'],
                    performance_score=ensemble_metrics['performance_score'],
                    risk_score=ensemble_metrics['risk_score'],
                    created_at=datetime.now()
                )
                
                ensembles.append(ensemble)
        
        return ensembles
    
    def _calculate_ensemble_metrics(self, strategies: List[Dict]) -> Dict:
        """Calculate ensemble performance metrics."""
        if not strategies:
            return {
                'total_score': 0.0,
                'diversification_score': 0.0,
                'performance_score': 0.0,
                'risk_score': 0.0,
                'weights': []
            }
        
        # Calculate performance score (weighted average)
        scores = [s['current_score'] for s in strategies]
        performance_score = sum(scores) / len(scores)
        
        # Calculate diversification score
        strategy_types = set(s['strategy_type'] for s in strategies)
        max_possible_types = len(strategies)
        diversification_score = len(strategy_types) / max_possible_types if max_possible_types > 0 else 0
        
        # Calculate risk score (standard deviation of scores)
        if len(scores) > 1:
            mean_score = sum(scores) / len(scores)
            variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)
            risk_score = variance ** 0.5
        else:
            risk_score = 0.0
        
        # Calculate weights (equal weight for now, could be optimized)
        weights = [1.0 / len(strategies)] * len(strategies)
        
        # Calculate total ensemble score
        total_score = (
            FLAGS.performance_weight * performance_score +
            FLAGS.diversification_weight * diversification_score
        ) - (0.1 * risk_score)  # Penalize high risk
        
        return {
            'total_score': total_score,
            'diversification_score': diversification_score,
            'performance_score': performance_score,
            'risk_score': risk_score,
            'weights': weights
        }
    
    def print_ensembles(self, ensembles: List[StrategyEnsemble], limit: int = 20):
        """Print ensembles in a formatted table."""
        print(f"\n{'='*120}")
        print("STRATEGY ENSEMBLES")
        print(f"{'='*120}")
        print(f"{'Symbol':<12} {'Ensemble ID':<25} {'Total Score':<12} {'Perf Score':<12} {'Div Score':<12} {'Risk Score':<12} {'Strategies':<20}")
        print(f"{'-'*120}")
        
        for ensemble in ensembles[:limit]:
            strategy_types = [s.strategy_type for s in ensemble.strategies]
            strategy_summary = f"{len(ensemble.strategies)} strategies: {', '.join(set(strategy_types))}"
            
            print(f"{ensemble.symbol:<12} {ensemble.ensemble_id:<25} "
                  f"{ensemble.total_score:<12.3f} {ensemble.performance_score:<12.3f} "
                  f"{ensemble.diversification_score:<12.3f} {ensemble.risk_score:<12.3f} "
                  f"{strategy_summary:<20}")
        
        if len(ensembles) > limit:
            print(f"... and {len(ensembles) - limit} more ensembles")
        print(f"{'='*120}")
    
    def print_ensemble_details(self, ensemble: StrategyEnsemble):
        """Print detailed information about a specific ensemble."""
        print(f"\n{'='*80}")
        print(f"ENSEMBLE DETAILS: {ensemble.ensemble_id}")
        print(f"{'='*80}")
        print(f"Symbol: {ensemble.symbol}")
        print(f"Total Score: {ensemble.total_score:.3f}")
        print(f"Performance Score: {ensemble.performance_score:.3f}")
        print(f"Diversification Score: {ensemble.diversification_score:.3f}")
        print(f"Risk Score: {ensemble.risk_score:.3f}")
        print(f"Created: {ensemble.created_at}")
        
        print(f"\n{'Strategies in Ensemble':<50} {'Score':<10} {'Weight':<10} {'Contribution':<12}")
        print(f"{'-'*80}")
        
        for strategy in ensemble.strategies:
            print(f"{strategy.strategy_type:<50} {strategy.current_score:<10.3f} "
                  f"{strategy.weight:<10.3f} {strategy.contribution:<12.3f}")
        
        print(f"{'='*80}")


def main(argv):
    """Main function."""
    if len(argv) > 1:
        raise app.UsageError("Too many command-line arguments")
    
    logging.set_verbosity(logging.INFO)
    logging.info("Starting Strategy Ensemble Builder")
    
    # Database configuration
    db_config = {
        "host": FLAGS.postgres_host,
        "port": FLAGS.postgres_port,
        "database": FLAGS.postgres_database,
        "user": FLAGS.postgres_username,
        "password": FLAGS.postgres_password,
    }
    
    ensemble_builder = StrategyEnsembleBuilder(db_config)
    
    async def run():
        try:
            await ensemble_builder.connect()
            
            # Get candidate strategies
            logging.info("Getting candidate strategies...")
            candidate_strategies = await ensemble_builder.get_candidate_strategies()
            
            print(f"\nCANDIDATE STRATEGIES:")
            print(f"Total strategies: {len(candidate_strategies)}")
            
            # Build ensembles
            logging.info("Building strategy ensembles...")
            ensembles = ensemble_builder.build_ensembles(candidate_strategies)
            
            # Sort by total score
            ensembles.sort(key=lambda x: x.total_score, reverse=True)
            
            # Print results
            ensemble_builder.print_ensembles(ensembles, limit=50)
            
            # Print summary statistics
            if ensembles:
                avg_total_score = sum(e.total_score for e in ensembles) / len(ensembles)
                avg_performance_score = sum(e.performance_score for e in ensembles) / len(ensembles)
                avg_diversification_score = sum(e.diversification_score for e in ensembles) / len(ensembles)
                avg_risk_score = sum(e.risk_score for e in ensembles) / len(ensembles)
                
                print(f"\nSUMMARY STATISTICS:")
                print(f"Total ensembles created: {len(ensembles)}")
                print(f"Average total score: {avg_total_score:.3f}")
                print(f"Average performance score: {avg_performance_score:.3f}")
                print(f"Average diversification score: {avg_diversification_score:.3f}")
                print(f"Average risk score: {avg_risk_score:.3f}")
                
                # Show top ensembles by symbol
                symbols = set(e.symbol for e in ensembles)
                print(f"\nTOP ENSEMBLES BY SYMBOL:")
                for symbol in sorted(symbols)[:5]:
                    symbol_ensembles = [e for e in ensembles if e.symbol == symbol]
                    symbol_ensembles.sort(key=lambda x: x.total_score, reverse=True)
                    if symbol_ensembles:
                        top_ensemble = symbol_ensembles[0]
                        print(f"{symbol}: {len(top_ensemble.strategies)} strategies (score: {top_ensemble.total_score:.3f})")
                
                # Show details of top ensemble
                if ensembles:
                    print(f"\nTOP ENSEMBLE DETAILS:")
                    ensemble_builder.print_ensemble_details(ensembles[0])
            
            logging.info("Strategy ensemble building completed successfully")
            
        except Exception as e:
            logging.exception(f"Error in strategy ensemble building: {e}")
            sys.exit(1)
        finally:
            await ensemble_builder.close()
    
    asyncio.run(run())


if __name__ == "__main__":
    app.run(main) 