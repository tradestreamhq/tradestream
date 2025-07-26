#!/usr/bin/env python3
"""
Strategy Confidence Scorer - Phase 1 Implementation

This service calculates confidence scores for strategies based on:
- Performance Score (60% weight)
- Discovery Frequency (25% weight) 
- Recency Factor (15% weight)

The confidence score helps prioritize strategies for live trading.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from absl import app, flags, logging

import asyncpg
from dataclasses import dataclass

FLAGS = flags.FLAGS

# Database Configuration
flags.DEFINE_string("postgres_host", "localhost", "PostgreSQL host")
flags.DEFINE_integer("postgres_port", 5432, "PostgreSQL port")
flags.DEFINE_string("postgres_database", "tradestream", "PostgreSQL database")
flags.DEFINE_string("postgres_username", "postgres", "PostgreSQL username")
flags.DEFINE_string("postgres_password", "tradestream123", "PostgreSQL password")

# Confidence Scoring Configuration
flags.DEFINE_float("performance_weight", 0.6, "Weight for performance score (0.0-1.0)")
flags.DEFINE_float("frequency_weight", 0.25, "Weight for discovery frequency (0.0-1.0)")
flags.DEFINE_float("recency_weight", 0.15, "Weight for recency factor (0.0-1.0)")
flags.DEFINE_integer("min_strategies_for_frequency", 5, "Minimum strategies needed for frequency calculation")
flags.DEFINE_integer("recency_days", 30, "Number of days to consider for recency calculation")

# Output Configuration
flags.DEFINE_string("output_topic", "strategy-confidence-scores", "Kafka topic for confidence scores")
flags.DEFINE_boolean("dry_run", False, "Run in dry-run mode (no Kafka output)")


@dataclass
class StrategyConfidenceScore:
    """Represents a strategy with its confidence score."""
    strategy_id: str
    symbol: str
    strategy_type: str
    current_score: float
    confidence_score: float
    performance_component: float
    frequency_component: float
    recency_component: float
    discovery_count: int
    days_since_discovery: int


class StrategyConfidenceScorer:
    """Calculates confidence scores for strategies."""
    
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
            
    async def get_strategy_statistics(self) -> Dict:
        """Get overall statistics for confidence calculation."""
        async with self.pool.acquire() as conn:
            # Get total strategies and max discovery count
            stats_query = """
            SELECT 
                COUNT(*) as total_strategies,
                MAX(discovery_count) as max_discovery_count,
                MIN(created_at) as oldest_strategy,
                MAX(created_at) as newest_strategy
            FROM (
                SELECT 
                    strategy_type,
                    COUNT(*) as discovery_count,
                    MIN(created_at) as created_at
                FROM strategies 
                GROUP BY strategy_type
            ) strategy_stats
            """
            
            row = await conn.fetchrow(stats_query)
            return {
                'total_strategies': row['total_strategies'] or 0,
                'max_discovery_count': row['max_discovery_count'] or 0,
                'oldest_strategy': row['oldest_strategy'],
                'newest_strategy': row['newest_strategy']
            }
    
    async def get_strategies_with_confidence(self, symbol: Optional[str] = None) -> List[StrategyConfidenceScore]:
        """Calculate confidence scores for all strategies or for a specific symbol."""
        stats = await self.get_strategy_statistics()
        
        # Build query
        if symbol:
            query = """
            SELECT 
                strategy_id,
                symbol,
                strategy_type,
                current_score,
                created_at,
                COUNT(*) OVER (PARTITION BY strategy_type) as discovery_count,
                EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400 as days_since_discovery
            FROM strategies 
            WHERE symbol = $1 AND is_active = TRUE
            ORDER BY current_score DESC
            """
            params = [symbol]
        else:
            query = """
            SELECT 
                strategy_id,
                symbol,
                strategy_type,
                current_score,
                created_at,
                COUNT(*) OVER (PARTITION BY strategy_type) as discovery_count,
                EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400 as days_since_discovery
            FROM strategies 
            WHERE is_active = TRUE
            ORDER BY current_score DESC
            """
            params = []
            
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
            confidence_scores = []
            for row in rows:
                confidence_score = self._calculate_confidence_score(
                    performance_score=row['current_score'],
                    discovery_count=row['discovery_count'],
                    days_since_discovery=row['days_since_discovery'],
                    max_discovery_count=stats['max_discovery_count'],
                    recency_days=FLAGS.recency_days
                )
                
                confidence_scores.append(StrategyConfidenceScore(
                    strategy_id=row['strategy_id'],
                    symbol=row['symbol'],
                    strategy_type=row['strategy_type'],
                    current_score=row['current_score'],
                    confidence_score=confidence_score['total'],
                    performance_component=confidence_score['performance'],
                    frequency_component=confidence_score['frequency'],
                    recency_component=confidence_score['recency'],
                    discovery_count=row['discovery_count'],
                    days_since_discovery=int(row['days_since_discovery'])
                ))
                
            return confidence_scores
    
    def _calculate_confidence_score(
        self,
        performance_score: float,
        discovery_count: int,
        days_since_discovery: float,
        max_discovery_count: int,
        recency_days: int
    ) -> Dict[str, float]:
        """Calculate confidence score components."""
        
        # Performance component (60% weight)
        performance_component = performance_score * FLAGS.performance_weight
        
        # Frequency component (25% weight)
        if max_discovery_count > 0:
            frequency_normalized = min(discovery_count / max_discovery_count, 1.0)
        else:
            frequency_normalized = 0.0
        frequency_component = frequency_normalized * FLAGS.frequency_weight
        
        # Recency component (15% weight)
        # Newer strategies get higher scores
        if days_since_discovery <= recency_days:
            recency_normalized = 1.0 - (days_since_discovery / recency_days)
        else:
            recency_normalized = 0.0
        recency_component = recency_normalized * FLAGS.recency_weight
        
        # Total confidence score
        total_confidence = performance_component + frequency_component + recency_component
        
        return {
            'total': total_confidence,
            'performance': performance_component,
            'frequency': frequency_component,
            'recency': recency_component
        }
    
    def print_confidence_scores(self, scores: List[StrategyConfidenceScore], limit: int = 20):
        """Print confidence scores in a formatted table."""
        print(f"\n{'='*80}")
        print("STRATEGY CONFIDENCE SCORES")
        print(f"{'='*80}")
        print(f"{'Symbol':<12} {'Strategy Type':<20} {'Score':<8} {'Confidence':<12} {'Freq':<6} {'Days':<6}")
        print(f"{'-'*80}")
        
        for score in scores[:limit]:
            print(f"{score.symbol:<12} {score.strategy_type:<20} "
                  f"{score.current_score:<8.3f} {score.confidence_score:<12.3f} "
                  f"{score.discovery_count:<6} {score.days_since_discovery:<6}")
        
        if len(scores) > limit:
            print(f"... and {len(scores) - limit} more strategies")
        print(f"{'='*80}")


def main(argv):
    """Main function."""
    if len(argv) > 1:
        raise app.UsageError("Too many command-line arguments")
    
    logging.set_verbosity(logging.INFO)
    logging.info("Starting Strategy Confidence Scorer")
    
    # Database configuration
    db_config = {
        "host": FLAGS.postgres_host,
        "port": FLAGS.postgres_port,
        "database": FLAGS.postgres_database,
        "user": FLAGS.postgres_username,
        "password": FLAGS.postgres_password,
    }
    
    scorer = StrategyConfidenceScorer(db_config)
    
    async def run():
        try:
            await scorer.connect()
            
            # Calculate confidence scores for all strategies
            logging.info("Calculating confidence scores...")
            confidence_scores = await scorer.get_strategies_with_confidence()
            
            # Sort by confidence score
            confidence_scores.sort(key=lambda x: x.confidence_score, reverse=True)
            
            # Print results
            scorer.print_confidence_scores(confidence_scores, limit=50)
            
            # Print summary statistics
            if confidence_scores:
                avg_confidence = sum(s.confidence_score for s in confidence_scores) / len(confidence_scores)
                max_confidence = max(s.confidence_score for s in confidence_scores)
                min_confidence = min(s.confidence_score for s in confidence_scores)
                
                print(f"\nSUMMARY STATISTICS:")
                print(f"Total strategies analyzed: {len(confidence_scores)}")
                print(f"Average confidence score: {avg_confidence:.3f}")
                print(f"Max confidence score: {max_confidence:.3f}")
                print(f"Min confidence score: {min_confidence:.3f}")
                
                # Show top strategies by symbol
                symbols = set(s.symbol for s in confidence_scores)
                print(f"\nTOP STRATEGIES BY SYMBOL:")
                for symbol in sorted(symbols)[:5]:  # Show first 5 symbols
                    symbol_scores = [s for s in confidence_scores if s.symbol == symbol]
                    symbol_scores.sort(key=lambda x: x.confidence_score, reverse=True)
                    if symbol_scores:
                        top_strategy = symbol_scores[0]
                        print(f"{symbol}: {top_strategy.strategy_type} (confidence: {top_strategy.confidence_score:.3f})")
            
            logging.info("Strategy confidence scoring completed successfully")
            
        except Exception as e:
            logging.exception(f"Error in strategy confidence scoring: {e}")
            sys.exit(1)
        finally:
            await scorer.close()
    
    asyncio.run(run())


if __name__ == "__main__":
    app.run(main) 