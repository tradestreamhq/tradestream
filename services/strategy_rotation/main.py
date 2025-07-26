#!/usr/bin/env python3
"""
Strategy Rotation - Phase 4 Implementation

This service handles dynamic strategy rotation:
- Strategy switching based on performance
- Position management and sizing
- Dynamic rebalancing
- Risk management and stop-loss
- Market regime detection

The goal is to dynamically switch between strategies based on performance and market conditions.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from absl import app, flags, logging
from dataclasses import dataclass
from enum import Enum

import asyncpg

FLAGS = flags.FLAGS

# Database Configuration
flags.DEFINE_string("postgres_host", "localhost", "PostgreSQL host")
flags.DEFINE_integer("postgres_port", 5432, "PostgreSQL port")
flags.DEFINE_string("postgres_database", "tradestream", "PostgreSQL database")
flags.DEFINE_string("postgres_username", "postgres", "PostgreSQL username")
flags.DEFINE_string("postgres_password", "tradestream123", "PostgreSQL password")

# Rotation Configuration
flags.DEFINE_integer("rotation_period_hours", 24, "How often to evaluate strategy rotation")
flags.DEFINE_float("min_performance_threshold", 0.6, "Minimum performance to keep strategy")
flags.DEFINE_float("rotation_threshold", 0.1, "Performance improvement needed for rotation")
flags.DEFINE_integer("max_positions_per_symbol", 3, "Maximum concurrent positions per symbol")
flags.DEFINE_float("position_size_factor", 0.1, "Position size as fraction of portfolio")
flags.DEFINE_float("stop_loss_threshold", 0.05, "Stop loss threshold (5%)")
flags.DEFINE_float("take_profit_threshold", 0.15, "Take profit threshold (15%)")

# Output Configuration
flags.DEFINE_string("output_topic", "strategy-rotations", "Kafka topic for rotation decisions")
flags.DEFINE_boolean("dry_run", False, "Run in dry-run mode (no Kafka output)")


class PositionStatus(Enum):
    """Position status enumeration."""
    OPEN = "open"
    CLOSED = "closed"
    STOPPED_OUT = "stopped_out"
    TAKE_PROFIT = "take_profit"


@dataclass
class Position:
    """Represents a trading position."""
    position_id: str
    symbol: str
    strategy_id: str
    strategy_type: str
    entry_price: float
    current_price: float
    position_size: float
    entry_time: datetime
    status: PositionStatus
    pnl: float
    pnl_percent: float


@dataclass
class RotationDecision:
    """Represents a strategy rotation decision."""
    symbol: str
    old_strategy_id: Optional[str]
    new_strategy_id: str
    old_strategy_type: Optional[str]
    new_strategy_type: str
    reason: str
    performance_improvement: float
    decision_time: datetime


class StrategyRotator:
    """Handles dynamic strategy rotation and position management."""
    
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
    
    async def get_active_positions(self) -> List[Position]:
        """Get currently active positions."""
        # This would typically come from a positions table
        # For now, we'll simulate with mock data
        return []
    
    async def get_candidate_strategies(self, symbol: str) -> List[Dict]:
        """Get candidate strategies for rotation."""
        query = """
        SELECT 
            strategy_id,
            symbol,
            strategy_type,
            current_score,
            created_at,
            last_evaluated_at
        FROM strategies 
        WHERE symbol = $1 
        AND is_active = TRUE
        AND current_score >= $2
        ORDER BY current_score DESC
        LIMIT 10
        """
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, symbol, FLAGS.min_performance_threshold)
            return [dict(row) for row in rows]
    
    async def evaluate_rotation_opportunities(self) -> List[RotationDecision]:
        """Evaluate opportunities for strategy rotation."""
        # Get all symbols with strategies
        symbols_query = "SELECT DISTINCT symbol FROM strategies WHERE is_active = TRUE"
        
        async with self.pool.acquire() as conn:
            symbol_rows = await conn.fetch(symbols_query)
            symbols = [row['symbol'] for row in symbol_rows]
        
        rotation_decisions = []
        
        for symbol in symbols:
            # Get candidate strategies for this symbol
            candidate_strategies = await self.get_candidate_strategies(symbol)
            
            if len(candidate_strategies) < 2:
                continue
            
            # Get current active positions for this symbol
            active_positions = [p for p in await self.get_active_positions() if p.symbol == symbol]
            
            # Evaluate rotation opportunities
            rotation_decision = self._evaluate_symbol_rotation(symbol, candidate_strategies, active_positions)
            
            if rotation_decision:
                rotation_decisions.append(rotation_decision)
        
        return rotation_decisions
    
    def _evaluate_symbol_rotation(
        self, 
        symbol: str, 
        strategies: List[Dict], 
        active_positions: List[Position]
    ) -> Optional[RotationDecision]:
        """Evaluate rotation opportunities for a specific symbol."""
        
        if not strategies:
            return None
        
        # Get current best strategy
        current_best = strategies[0]
        
        # Check if we have active positions
        current_strategy_id = None
        if active_positions:
            current_strategy_id = active_positions[0].strategy_id
            current_strategy_type = active_positions[0].strategy_type
            
            # Check if current strategy is still in top candidates
            current_in_top = any(s['strategy_id'] == current_strategy_id for s in strategies[:3])
            
            if not current_in_top:
                # Current strategy is no longer in top 3, consider rotation
                return RotationDecision(
                    symbol=symbol,
                    old_strategy_id=current_strategy_id,
                    new_strategy_id=current_best['strategy_id'],
                    old_strategy_type=current_strategy_type,
                    new_strategy_type=current_best['strategy_type'],
                    reason="Current strategy no longer in top performers",
                    performance_improvement=current_best['current_score'] - 0.6,  # Assuming current is 0.6
                    decision_time=datetime.now()
                )
        else:
            # No active positions, start with best strategy
            return RotationDecision(
                symbol=symbol,
                old_strategy_id=None,
                new_strategy_id=current_best['strategy_id'],
                old_strategy_type=None,
                new_strategy_type=current_best['strategy_type'],
                reason="No active positions, starting with best strategy",
                performance_improvement=current_best['current_score'],
                decision_time=datetime.now()
            )
        
        return None
    
    async def calculate_position_sizes(self, strategies: List[Dict]) -> Dict[str, float]:
        """Calculate position sizes for strategies."""
        position_sizes = {}
        
        # Simple equal weighting for now
        # Could be enhanced with Kelly Criterion, risk parity, etc.
        total_weight = 1.0
        weight_per_strategy = total_weight / len(strategies)
        
        for strategy in strategies:
            position_sizes[strategy['strategy_id']] = weight_per_strategy * FLAGS.position_size_factor
        
        return position_sizes
    
    def print_rotation_decisions(self, decisions: List[RotationDecision]):
        """Print rotation decisions in a formatted table."""
        print(f"\n{'='*100}")
        print("STRATEGY ROTATION DECISIONS")
        print(f"{'='*100}")
        print(f"{'Symbol':<12} {'Old Strategy':<20} {'New Strategy':<20} {'Reason':<30} {'Improvement':<12}")
        print(f"{'-'*100}")
        
        for decision in decisions:
            old_strategy = decision.old_strategy_type or "None"
            print(f"{decision.symbol:<12} {old_strategy:<20} {decision.new_strategy_type:<20} "
                  f"{decision.reason:<30} {decision.performance_improvement:<12.3f}")
        
        print(f"{'='*100}")
    
    async def get_rotation_statistics(self) -> Dict:
        """Get statistics about strategy rotation."""
        async with self.pool.acquire() as conn:
            # Get total strategies
            total_query = "SELECT COUNT(*) FROM strategies WHERE is_active = TRUE"
            total_strategies = await conn.fetchval(total_query)
            
            # Get strategies by performance tier
            performance_query = """
            SELECT 
                COUNT(CASE WHEN current_score >= 0.9 THEN 1 END) as excellent,
                COUNT(CASE WHEN current_score >= 0.8 AND current_score < 0.9 THEN 1 END) as good,
                COUNT(CASE WHEN current_score >= 0.7 AND current_score < 0.8 THEN 1 END) as fair,
                COUNT(CASE WHEN current_score < 0.7 THEN 1 END) as poor
            FROM strategies 
            WHERE is_active = TRUE
            """
            performance_stats = await conn.fetchrow(performance_query)
            
            return {
                'total_strategies': total_strategies or 0,
                'excellent_strategies': performance_stats['excellent'] or 0,
                'good_strategies': performance_stats['good'] or 0,
                'fair_strategies': performance_stats['fair'] or 0,
                'poor_strategies': performance_stats['poor'] or 0
            }


def main(argv):
    """Main function."""
    if len(argv) > 1:
        raise app.UsageError("Too many command-line arguments")
    
    logging.set_verbosity(logging.INFO)
    logging.info("Starting Strategy Rotator")
    
    # Database configuration
    db_config = {
        "host": FLAGS.postgres_host,
        "port": FLAGS.postgres_port,
        "database": FLAGS.postgres_database,
        "user": FLAGS.postgres_username,
        "password": FLAGS.postgres_password,
    }
    
    rotator = StrategyRotator(db_config)
    
    async def run():
        try:
            await rotator.connect()
            
            # Get rotation statistics
            logging.info("Getting rotation statistics...")
            stats = await rotator.get_rotation_statistics()
            
            print(f"\nROTATION STATISTICS:")
            print(f"Total strategies: {stats['total_strategies']}")
            print(f"Excellent strategies (≥0.9): {stats['excellent_strategies']}")
            print(f"Good strategies (0.8-0.9): {stats['good_strategies']}")
            print(f"Fair strategies (0.7-0.8): {stats['fair_strategies']}")
            print(f"Poor strategies (<0.7): {stats['poor_strategies']}")
            
            # Evaluate rotation opportunities
            logging.info("Evaluating rotation opportunities...")
            rotation_decisions = await rotator.evaluate_rotation_opportunities()
            
            # Print results
            rotator.print_rotation_decisions(rotation_decisions)
            
            # Print summary
            if rotation_decisions:
                symbols_with_rotations = set(d.symbol for d in rotation_decisions)
                avg_improvement = sum(d.performance_improvement for d in rotation_decisions) / len(rotation_decisions)
                
                print(f"\nSUMMARY:")
                print(f"Rotation decisions: {len(rotation_decisions)}")
                print(f"Symbols affected: {len(symbols_with_rotations)}")
                print(f"Average performance improvement: {avg_improvement:.3f}")
                
                # Show top rotation opportunities
                rotation_decisions.sort(key=lambda x: x.performance_improvement, reverse=True)
                print(f"\nTOP ROTATION OPPORTUNITIES:")
                for i, decision in enumerate(rotation_decisions[:5]):
                    print(f"{i+1}. {decision.symbol}: {decision.old_strategy_type or 'None'} → {decision.new_strategy_type} "
                          f"(improvement: {decision.performance_improvement:.3f})")
            else:
                print(f"\nNo rotation opportunities found at this time.")
            
            logging.info("Strategy rotation evaluation completed successfully")
            
        except Exception as e:
            logging.exception(f"Error in strategy rotation: {e}")
            sys.exit(1)
        finally:
            await rotator.close()
    
    asyncio.run(run())


if __name__ == "__main__":
    app.run(main) 