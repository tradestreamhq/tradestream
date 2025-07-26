#!/usr/bin/env python3
"""
Strategy Time Filter - Phase 2 Implementation

This service filters strategies based on:
- Discovery time period (when strategy was discovered)
- Backtesting window constraints
- Market regime alignment
- Time-based performance decay

The goal is to ensure strategies are only used during their validated time periods.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from absl import app, flags, logging
from dataclasses import dataclass

import asyncpg

FLAGS = flags.FLAGS

# Database Configuration
flags.DEFINE_string("postgres_host", "localhost", "PostgreSQL host")
flags.DEFINE_integer("postgres_port", 5432, "PostgreSQL port")
flags.DEFINE_string("postgres_database", "tradestream", "PostgreSQL database")
flags.DEFINE_string("postgres_username", "postgres", "PostgreSQL username")
flags.DEFINE_string("postgres_password", "tradestream123", "PostgreSQL password")

# Time Filtering Configuration
flags.DEFINE_integer("max_strategy_age_days", 90, "Maximum age of strategies to consider")
flags.DEFINE_integer("min_backtest_window_days", 30, "Minimum backtesting window required")
flags.DEFINE_integer("max_backtest_window_days", 365, "Maximum backtesting window allowed")
flags.DEFINE_float("time_decay_factor", 0.1, "Performance decay per month after discovery")
flags.DEFINE_boolean("require_recent_discovery", True, "Require strategies to be discovered recently")

# Output Configuration
flags.DEFINE_string("output_topic", "time-filtered-strategies", "Kafka topic for filtered strategies")
flags.DEFINE_boolean("dry_run", False, "Run in dry-run mode (no Kafka output)")


@dataclass
class TimeFilteredStrategy:
    """Represents a strategy that passed time-based filtering."""
    strategy_id: str
    symbol: str
    strategy_type: str
    current_score: float
    discovery_start_time: datetime
    discovery_end_time: datetime
    created_at: datetime
    days_since_discovery: int
    backtest_window_days: int
    time_adjusted_score: float
    is_recent: bool
    is_valid_window: bool


class StrategyTimeFilter:
    """Filters strategies based on time constraints."""
    
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
    
    async def get_time_filtered_strategies(self, symbol: Optional[str] = None) -> List[TimeFilteredStrategy]:
        """Get strategies that pass time-based filtering."""
        
        # Build base query
        base_query = """
        SELECT 
            strategy_id,
            symbol,
            strategy_type,
            current_score,
            discovery_start_time,
            discovery_end_time,
            created_at,
            EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400 as days_since_discovery,
            CASE 
                WHEN discovery_start_time IS NOT NULL AND discovery_end_time IS NOT NULL 
                THEN EXTRACT(EPOCH FROM (discovery_end_time - discovery_start_time)) / 86400
                ELSE NULL 
            END as backtest_window_days
        FROM strategies 
        WHERE is_active = TRUE
        """
        
        if symbol:
            base_query += " AND symbol = $1"
            params = [symbol]
        else:
            params = []
            
        base_query += " ORDER BY current_score DESC"
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(base_query, *params)
            
            filtered_strategies = []
            for row in rows:
                # Apply time-based filtering
                time_filter_result = self._apply_time_filters(
                    days_since_discovery=row['days_since_discovery'],
                    backtest_window_days=row['backtest_window_days'],
                    current_score=row['current_score']
                )
                
                if time_filter_result['is_valid']:
                    filtered_strategies.append(TimeFilteredStrategy(
                        strategy_id=row['strategy_id'],
                        symbol=row['symbol'],
                        strategy_type=row['strategy_type'],
                        current_score=row['current_score'],
                        discovery_start_time=row['discovery_start_time'],
                        discovery_end_time=row['discovery_end_time'],
                        created_at=row['created_at'],
                        days_since_discovery=int(row['days_since_discovery']),
                        backtest_window_days=int(row['backtest_window_days']) if row['backtest_window_days'] else 0,
                        time_adjusted_score=time_filter_result['adjusted_score'],
                        is_recent=time_filter_result['is_recent'],
                        is_valid_window=time_filter_result['is_valid_window']
                    ))
            
            return filtered_strategies
    
    def _apply_time_filters(
        self,
        days_since_discovery: float,
        backtest_window_days: Optional[float],
        current_score: float
    ) -> Dict:
        """Apply time-based filtering rules."""
        
        # Check if strategy is too old
        is_recent = days_since_discovery <= FLAGS.max_strategy_age_days
        
        # Check if backtest window is valid
        is_valid_window = True
        if backtest_window_days is not None:
            is_valid_window = (
                backtest_window_days >= FLAGS.min_backtest_window_days and
                backtest_window_days <= FLAGS.max_backtest_window_days
            )
        
        # Calculate time-adjusted score
        months_since_discovery = days_since_discovery / 30.0
        time_decay = months_since_discovery * FLAGS.time_decay_factor
        adjusted_score = max(0.0, current_score - time_decay)
        
        # Determine if strategy passes all filters
        is_valid = True
        if FLAGS.require_recent_discovery:
            is_valid = is_valid and is_recent
        is_valid = is_valid and is_valid_window
        
        return {
            'is_valid': is_valid,
            'is_recent': is_recent,
            'is_valid_window': is_valid_window,
            'adjusted_score': adjusted_score,
            'time_decay': time_decay
        }
    
    def print_filtered_strategies(self, strategies: List[TimeFilteredStrategy], limit: int = 20):
        """Print filtered strategies in a formatted table."""
        print(f"\n{'='*100}")
        print("TIME-FILTERED STRATEGIES")
        print(f"{'='*100}")
        print(f"{'Symbol':<12} {'Strategy Type':<20} {'Score':<8} {'Adj Score':<10} {'Days':<6} {'Window':<8} {'Recent':<8} {'Valid':<6}")
        print(f"{'-'*100}")
        
        for strategy in strategies[:limit]:
            print(f"{strategy.symbol:<12} {strategy.strategy_type:<20} "
                  f"{strategy.current_score:<8.3f} {strategy.time_adjusted_score:<10.3f} "
                  f"{strategy.days_since_discovery:<6} {strategy.backtest_window_days:<8} "
                  f"{'✓' if strategy.is_recent else '✗':<8} {'✓' if strategy.is_valid_window else '✗':<6}")
        
        if len(strategies) > limit:
            print(f"... and {len(strategies) - limit} more strategies")
        print(f"{'='*100}")
    
    async def get_filtering_statistics(self) -> Dict:
        """Get statistics about the filtering process."""
        async with self.pool.acquire() as conn:
            # Get total strategies
            total_query = "SELECT COUNT(*) FROM strategies WHERE is_active = TRUE"
            total_strategies = await conn.fetchval(total_query)
            
            # Get strategies by age
            age_query = """
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400 <= $1 THEN 1 END) as recent,
                COUNT(CASE WHEN EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400 > $1 THEN 1 END) as old
            FROM strategies 
            WHERE is_active = TRUE
            """
            age_stats = await conn.fetchrow(age_query, FLAGS.max_strategy_age_days)
            
            # Get strategies by backtest window
            window_query = """
            SELECT 
                COUNT(*) as total,
                COUNT(CASE 
                    WHEN EXTRACT(EPOCH FROM (discovery_end_time - discovery_start_time)) / 86400 >= $1 
                    AND EXTRACT(EPOCH FROM (discovery_end_time - discovery_start_time)) / 86400 <= $2 
                    THEN 1 
                END) as valid_window,
                COUNT(CASE 
                    WHEN EXTRACT(EPOCH FROM (discovery_end_time - discovery_start_time)) / 86400 < $1 
                    OR EXTRACT(EPOCH FROM (discovery_end_time - discovery_start_time)) / 86400 > $2 
                    THEN 1 
                END) as invalid_window
            FROM strategies 
            WHERE is_active = TRUE 
            AND discovery_start_time IS NOT NULL 
            AND discovery_end_time IS NOT NULL
            """
            window_stats = await conn.fetchrow(window_query, FLAGS.min_backtest_window_days, FLAGS.max_backtest_window_days)
            
            return {
                'total_strategies': total_strategies or 0,
                'recent_strategies': age_stats['recent'] or 0,
                'old_strategies': age_stats['old'] or 0,
                'valid_window_strategies': window_stats['valid_window'] or 0,
                'invalid_window_strategies': window_stats['invalid_window'] or 0
            }


def main(argv):
    """Main function."""
    if len(argv) > 1:
        raise app.UsageError("Too many command-line arguments")
    
    logging.set_verbosity(logging.INFO)
    logging.info("Starting Strategy Time Filter")
    
    # Database configuration
    db_config = {
        "host": FLAGS.postgres_host,
        "port": FLAGS.postgres_port,
        "database": FLAGS.postgres_database,
        "user": FLAGS.postgres_username,
        "password": FLAGS.postgres_password,
    }
    
    time_filter = StrategyTimeFilter(db_config)
    
    async def run():
        try:
            await time_filter.connect()
            
            # Get filtering statistics
            logging.info("Getting filtering statistics...")
            stats = await time_filter.get_filtering_statistics()
            
            print(f"\nFILTERING STATISTICS:")
            print(f"Total strategies: {stats['total_strategies']}")
            print(f"Recent strategies (≤{FLAGS.max_strategy_age_days} days): {stats['recent_strategies']}")
            print(f"Old strategies (> {FLAGS.max_strategy_age_days} days): {stats['old_strategies']}")
            print(f"Valid window strategies: {stats['valid_window_strategies']}")
            print(f"Invalid window strategies: {stats['invalid_window_strategies']}")
            
            # Get time-filtered strategies
            logging.info("Applying time-based filters...")
            filtered_strategies = await time_filter.get_time_filtered_strategies()
            
            # Sort by time-adjusted score
            filtered_strategies.sort(key=lambda x: x.time_adjusted_score, reverse=True)
            
            # Print results
            time_filter.print_filtered_strategies(filtered_strategies, limit=50)
            
            # Print summary
            if filtered_strategies:
                avg_adjusted_score = sum(s.time_adjusted_score for s in filtered_strategies) / len(filtered_strategies)
                max_adjusted_score = max(s.time_adjusted_score for s in filtered_strategies)
                min_adjusted_score = min(s.time_adjusted_score for s in filtered_strategies)
                
                print(f"\nSUMMARY:")
                print(f"Strategies passing time filters: {len(filtered_strategies)}")
                print(f"Average adjusted score: {avg_adjusted_score:.3f}")
                print(f"Max adjusted score: {max_adjusted_score:.3f}")
                print(f"Min adjusted score: {min_adjusted_score:.3f}")
                
                # Show top strategies by symbol
                symbols = set(s.symbol for s in filtered_strategies)
                print(f"\nTOP TIME-FILTERED STRATEGIES BY SYMBOL:")
                for symbol in sorted(symbols)[:5]:
                    symbol_strategies = [s for s in filtered_strategies if s.symbol == symbol]
                    symbol_strategies.sort(key=lambda x: x.time_adjusted_score, reverse=True)
                    if symbol_strategies:
                        top_strategy = symbol_strategies[0]
                        print(f"{symbol}: {top_strategy.strategy_type} (adjusted score: {top_strategy.time_adjusted_score:.3f})")
            
            logging.info("Strategy time filtering completed successfully")
            
        except Exception as e:
            logging.exception(f"Error in strategy time filtering: {e}")
            sys.exit(1)
        finally:
            await time_filter.close()
    
    asyncio.run(run())


if __name__ == "__main__":
    app.run(main) 