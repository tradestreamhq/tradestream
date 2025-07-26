#!/usr/bin/env python3
"""
Risk-Adjusted Sizing - Phase 5 Implementation

This service calculates optimal position sizes based on:
- Strategy confidence scores
- Historical volatility
- Portfolio risk constraints
- Kelly Criterion
- Risk parity principles
- Maximum drawdown limits

The goal is to optimize position sizes for maximum risk-adjusted returns.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from absl import app, flags, logging
from dataclasses import dataclass
import math

import asyncpg

FLAGS = flags.FLAGS

# Database Configuration
flags.DEFINE_string("postgres_host", "localhost", "PostgreSQL host")
flags.DEFINE_integer("postgres_port", 5432, "PostgreSQL port")
flags.DEFINE_string("postgres_database", "tradestream", "PostgreSQL database")
flags.DEFINE_string("postgres_username", "postgres", "PostgreSQL username")
flags.DEFINE_string("postgres_password", "tradestream123", "PostgreSQL password")

# Risk Configuration
flags.DEFINE_float("max_portfolio_risk", 0.02, "Maximum portfolio risk (2%)")
flags.DEFINE_float("max_position_risk", 0.005, "Maximum position risk (0.5%)")
flags.DEFINE_float("risk_free_rate", 0.02, "Risk-free rate (2%)")
flags.DEFINE_float("kelly_fraction", 0.25, "Fraction of Kelly Criterion to use")
flags.DEFINE_float("max_leverage", 2.0, "Maximum leverage allowed")
flags.DEFINE_float("volatility_lookback_days", 30, "Days to calculate volatility")

# Output Configuration
flags.DEFINE_string("output_topic", "risk-adjusted-positions", "Kafka topic for position sizes")
flags.DEFINE_boolean("dry_run", False, "Run in dry-run mode (no Kafka output)")


@dataclass
class RiskMetrics:
    """Risk metrics for a strategy."""
    strategy_id: str
    symbol: str
    strategy_type: str
    current_score: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float


@dataclass
class PositionSize:
    """Calculated position size with risk metrics."""
    strategy_id: str
    symbol: str
    strategy_type: str
    confidence_score: float
    kelly_size: float
    risk_parity_size: float
    volatility_adjusted_size: float
    final_size: float
    risk_contribution: float
    expected_return: float


class RiskAdjustedSizer:
    """Calculates risk-adjusted position sizes."""
    
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
    
    async def get_strategies_with_risk_metrics(self) -> List[RiskMetrics]:
        """Get strategies with calculated risk metrics."""
        query = """
        SELECT 
            strategy_id,
            symbol,
            strategy_type,
            current_score,
            -- Placeholder risk metrics (would come from actual calculations)
            0.15 as volatility,
            1.2 as sharpe_ratio,
            0.05 as max_drawdown,
            0.65 as win_rate,
            1.8 as profit_factor
        FROM strategies 
        WHERE is_active = TRUE
        AND current_score >= 0.6
        ORDER BY current_score DESC
        """
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
            
            risk_metrics = []
            for row in rows:
                risk_metrics.append(RiskMetrics(
                    strategy_id=row['strategy_id'],
                    symbol=row['symbol'],
                    strategy_type=row['strategy_type'],
                    current_score=row['current_score'],
                    volatility=row['volatility'],
                    sharpe_ratio=row['sharpe_ratio'],
                    max_drawdown=row['max_drawdown'],
                    win_rate=row['win_rate'],
                    profit_factor=row['profit_factor']
                ))
            
            return risk_metrics
    
    def calculate_kelly_criterion(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Calculate Kelly Criterion position size."""
        if avg_loss == 0:
            return 0.0
        
        # Kelly formula: f = (bp - q) / b
        # where b = odds received, p = probability of win, q = probability of loss
        b = avg_win / avg_loss  # odds received
        p = win_rate
        q = 1 - win_rate
        
        kelly_fraction = (b * p - q) / b
        
        # Apply Kelly fraction and cap at maximum
        return min(max(kelly_fraction * FLAGS.kelly_fraction, 0.0), FLAGS.max_leverage)
    
    def calculate_risk_parity_size(self, volatility: float, target_risk: float) -> float:
        """Calculate position size for risk parity."""
        if volatility == 0:
            return 0.0
        
        # Risk parity: equal risk contribution
        # Position size = target_risk / volatility
        return target_risk / volatility
    
    def calculate_volatility_adjusted_size(self, score: float, volatility: float) -> float:
        """Calculate volatility-adjusted position size."""
        if volatility == 0:
            return 0.0
        
        # Higher score and lower volatility = larger position
        volatility_factor = 1.0 / (1.0 + volatility)
        score_factor = score
        
        return score_factor * volatility_factor
    
    def calculate_position_sizes(self, risk_metrics: List[RiskMetrics]) -> List[PositionSize]:
        """Calculate position sizes for all strategies."""
        position_sizes = []
        
        for metrics in risk_metrics:
            # Calculate Kelly Criterion
            # Using simplified assumptions for win/loss ratios
            avg_win = metrics.profit_factor * 0.02  # 2% average win
            avg_loss = 0.02  # 2% average loss
            kelly_size = self.calculate_kelly_criterion(metrics.win_rate, avg_win, avg_loss)
            
            # Calculate risk parity size
            target_risk = FLAGS.max_position_risk
            risk_parity_size = self.calculate_risk_parity_size(metrics.volatility, target_risk)
            
            # Calculate volatility-adjusted size
            volatility_adjusted_size = self.calculate_volatility_adjusted_size(
                metrics.current_score, metrics.volatility
            )
            
            # Combine all methods (weighted average)
            final_size = (
                0.4 * kelly_size +
                0.3 * risk_parity_size +
                0.3 * volatility_adjusted_size
            )
            
            # Apply constraints
            final_size = min(final_size, FLAGS.max_leverage)
            final_size = max(final_size, 0.0)
            
            # Calculate risk contribution
            risk_contribution = final_size * metrics.volatility
            
            # Calculate expected return
            expected_return = metrics.current_score * final_size - FLAGS.risk_free_rate * final_size
            
            position_sizes.append(PositionSize(
                strategy_id=metrics.strategy_id,
                symbol=metrics.symbol,
                strategy_type=metrics.strategy_type,
                confidence_score=metrics.current_score,
                kelly_size=kelly_size,
                risk_parity_size=risk_parity_size,
                volatility_adjusted_size=volatility_adjusted_size,
                final_size=final_size,
                risk_contribution=risk_contribution,
                expected_return=expected_return
            ))
        
        return position_sizes
    
    def print_position_sizes(self, position_sizes: List[PositionSize], limit: int = 20):
        """Print position sizes in a formatted table."""
        print(f"\n{'='*140}")
        print("RISK-ADJUSTED POSITION SIZES")
        print(f"{'='*140}")
        print(f"{'Symbol':<12} {'Strategy Type':<20} {'Confidence':<12} {'Kelly':<8} {'Risk Parity':<12} {'Vol Adj':<10} {'Final':<8} {'Risk':<8} {'Return':<10}")
        print(f"{'-'*140}")
        
        for position in position_sizes[:limit]:
            print(f"{position.symbol:<12} {position.strategy_type:<20} "
                  f"{position.confidence_score:<12.3f} {position.kelly_size:<8.3f} "
                  f"{position.risk_parity_size:<12.3f} {position.volatility_adjusted_size:<10.3f} "
                  f"{position.final_size:<8.3f} {position.risk_contribution:<8.3f} "
                  f"{position.expected_return:<10.3f}")
        
        if len(position_sizes) > limit:
            print(f"... and {len(position_sizes) - limit} more positions")
        print(f"{'='*140}")
    
    async def get_sizing_statistics(self) -> Dict:
        """Get statistics about position sizing."""
        async with self.pool.acquire() as conn:
            # Get total strategies
            total_query = "SELECT COUNT(*) FROM strategies WHERE is_active = TRUE AND current_score >= 0.6"
            total_strategies = await conn.fetchval(total_query)
            
            # Get strategies by confidence tier
            confidence_query = """
            SELECT 
                COUNT(CASE WHEN current_score >= 0.9 THEN 1 END) as high_confidence,
                COUNT(CASE WHEN current_score >= 0.8 AND current_score < 0.9 THEN 1 END) as medium_confidence,
                COUNT(CASE WHEN current_score >= 0.6 AND current_score < 0.8 THEN 1 END) as low_confidence
            FROM strategies 
            WHERE is_active = TRUE
            AND current_score >= 0.6
            """
            confidence_stats = await conn.fetchrow(confidence_query)
            
            return {
                'total_strategies': total_strategies or 0,
                'high_confidence': confidence_stats['high_confidence'] or 0,
                'medium_confidence': confidence_stats['medium_confidence'] or 0,
                'low_confidence': confidence_stats['low_confidence'] or 0
            }


def main(argv):
    """Main function."""
    if len(argv) > 1:
        raise app.UsageError("Too many command-line arguments")
    
    logging.set_verbosity(logging.INFO)
    logging.info("Starting Risk-Adjusted Sizer")
    
    # Database configuration
    db_config = {
        "host": FLAGS.postgres_host,
        "port": FLAGS.postgres_port,
        "database": FLAGS.postgres_database,
        "user": FLAGS.postgres_username,
        "password": FLAGS.postgres_password,
    }
    
    sizer = RiskAdjustedSizer(db_config)
    
    async def run():
        try:
            await sizer.connect()
            
            # Get sizing statistics
            logging.info("Getting sizing statistics...")
            stats = await sizer.get_sizing_statistics()
            
            print(f"\nSIZING STATISTICS:")
            print(f"Total strategies: {stats['total_strategies']}")
            print(f"High confidence (≥0.9): {stats['high_confidence']}")
            print(f"Medium confidence (0.8-0.9): {stats['medium_confidence']}")
            print(f"Low confidence (0.6-0.8): {stats['low_confidence']}")
            
            # Get strategies with risk metrics
            logging.info("Getting strategies with risk metrics...")
            risk_metrics = await sizer.get_strategies_with_risk_metrics()
            
            # Calculate position sizes
            logging.info("Calculating position sizes...")
            position_sizes = sizer.calculate_position_sizes(risk_metrics)
            
            # Sort by expected return
            position_sizes.sort(key=lambda x: x.expected_return, reverse=True)
            
            # Print results
            sizer.print_position_sizes(position_sizes, limit=50)
            
            # Print summary statistics
            if position_sizes:
                avg_final_size = sum(p.final_size for p in position_sizes) / len(position_sizes)
                avg_risk_contribution = sum(p.risk_contribution for p in position_sizes) / len(position_sizes)
                avg_expected_return = sum(p.expected_return for p in position_sizes) / len(position_sizes)
                total_risk = sum(p.risk_contribution for p in position_sizes)
                
                print(f"\nSUMMARY STATISTICS:")
                print(f"Total positions calculated: {len(position_sizes)}")
                print(f"Average position size: {avg_final_size:.3f}")
                print(f"Average risk contribution: {avg_risk_contribution:.3f}")
                print(f"Average expected return: {avg_expected_return:.3f}")
                print(f"Total portfolio risk: {total_risk:.3f}")
                
                # Show top positions by expected return
                symbols = set(p.symbol for p in position_sizes)
                print(f"\nTOP POSITIONS BY EXPECTED RETURN:")
                for symbol in sorted(symbols)[:5]:
                    symbol_positions = [p for p in position_sizes if p.symbol == symbol]
                    symbol_positions.sort(key=lambda x: x.expected_return, reverse=True)
                    if symbol_positions:
                        top_position = symbol_positions[0]
                        print(f"{symbol}: {top_position.strategy_type} "
                              f"(size: {top_position.final_size:.3f}, return: {top_position.expected_return:.3f})")
                
                # Show risk allocation by symbol
                print(f"\nRISK ALLOCATION BY SYMBOL:")
                for symbol in sorted(symbols)[:5]:
                    symbol_positions = [p for p in position_sizes if p.symbol == symbol]
                    total_symbol_risk = sum(p.risk_contribution for p in symbol_positions)
                    print(f"{symbol}: {total_symbol_risk:.3f} risk contribution")
            
            logging.info("Risk-adjusted sizing completed successfully")
            
        except Exception as e:
            logging.exception(f"Error in risk-adjusted sizing: {e}")
            sys.exit(1)
        finally:
            await sizer.close()
    
    asyncio.run(run())


if __name__ == "__main__":
    app.run(main) 