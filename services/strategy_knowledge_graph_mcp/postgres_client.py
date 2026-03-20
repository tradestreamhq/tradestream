"""
PostgreSQL client for the Strategy Knowledge Graph MCP server.
Handles queries for indicator relationships, market condition mappings,
strategy recommendations, composite strategies, and performance attribution.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

postgres_retry_params = dict(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(
        (
            asyncpg.ConnectionDoesNotExistError,
            asyncpg.ConnectionFailureError,
            asyncpg.QueryCanceledError,
            asyncpg.PostgresError,
        )
    ),
    reraise=True,
)


class PostgresClient:
    """Async PostgreSQL client for strategy knowledge graph queries."""

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        min_connections: int = 1,
        max_connections: int = 10,
    ):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.pool: Optional[asyncpg.Pool] = None

    @retry(**postgres_retry_params)
    async def connect(self) -> None:
        """Establish connection pool to PostgreSQL."""
        try:
            logging.info(
                f"Connecting to PostgreSQL at {self.host}:{self.port}/{self.database}"
            )
            self.pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password,
                min_size=self.min_connections,
                max_size=self.max_connections,
                command_timeout=60,
                server_settings={
                    "application_name": "strategy_knowledge_graph_mcp",
                },
            )
            async with self.pool.acquire() as conn:
                await conn.execute("SELECT 1")
            logging.info("Successfully connected to PostgreSQL")
        except Exception as e:
            logging.error(f"Failed to connect to PostgreSQL: {e}")
            self.pool = None
            raise

    async def close(self) -> None:
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            logging.info("PostgreSQL connection pool closed")

    def _ensure_pool(self) -> None:
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

    # ── Indicator Relationships ──────────────────────────────────────────

    async def get_indicator_relationships(
        self,
        indicator_name: Optional[str] = None,
        relationship_type: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Get indicator relationships, optionally filtered by indicator or type."""
        self._ensure_pool()

        params: List[Any] = []
        conditions: List[str] = []
        param_idx = 1

        if indicator_name:
            conditions.append(
                f"(a.name = ${param_idx} OR b.name = ${param_idx})"
            )
            params.append(indicator_name.upper())
            param_idx += 1

        if relationship_type:
            conditions.append(f"ir.relationship_type = ${param_idx}")
            params.append(relationship_type)
            param_idx += 1

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
        SELECT
            a.name AS indicator_a,
            a.category AS category_a,
            b.name AS indicator_b,
            b.category AS category_b,
            ir.relationship_type,
            ir.strength,
            ir.reasoning
        FROM indicator_relationships ir
        JOIN indicator_catalog a ON ir.indicator_a = a.id
        JOIN indicator_catalog b ON ir.indicator_b = b.id
        {where_clause}
        ORDER BY ir.strength DESC
        LIMIT ${param_idx}
        """
        params.append(limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        items = []
        for row in rows:
            items.append({
                "indicator_a": row["indicator_a"],
                "category_a": row["category_a"],
                "indicator_b": row["indicator_b"],
                "category_b": row["category_b"],
                "relationship_type": row["relationship_type"],
                "strength": float(row["strength"]),
                "reasoning": row["reasoning"],
            })

        return {"items": items, "count": len(items)}

    async def get_complementary_indicators(
        self, indicator_name: str, min_strength: float = 0.5
    ) -> Dict[str, Any]:
        """Find indicators that complement the given indicator."""
        self._ensure_pool()

        query = """
        SELECT
            CASE WHEN a.name = $1 THEN b.name ELSE a.name END AS complementary_indicator,
            CASE WHEN a.name = $1 THEN b.category ELSE a.category END AS category,
            ir.strength,
            ir.reasoning
        FROM indicator_relationships ir
        JOIN indicator_catalog a ON ir.indicator_a = a.id
        JOIN indicator_catalog b ON ir.indicator_b = b.id
        WHERE (a.name = $1 OR b.name = $1)
          AND ir.relationship_type = 'complementary'
          AND ir.strength >= $2
        ORDER BY ir.strength DESC
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, indicator_name.upper(), min_strength)

        items = []
        for row in rows:
            items.append({
                "indicator": row["complementary_indicator"],
                "category": row["category"],
                "strength": float(row["strength"]),
                "reasoning": row["reasoning"],
            })

        return {"indicator": indicator_name.upper(), "complementary": items}

    # ── Market Conditions ────────────────────────────────────────────────

    async def get_market_conditions(
        self,
        trend: Optional[str] = None,
        volatility: Optional[str] = None,
        volume: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get market condition taxonomy entries, optionally filtered."""
        self._ensure_pool()

        params: List[Any] = []
        conditions: List[str] = []
        param_idx = 1

        if trend:
            conditions.append(f"trend = ${param_idx}")
            params.append(trend)
            param_idx += 1
        if volatility:
            conditions.append(f"volatility = ${param_idx}")
            params.append(volatility)
            param_idx += 1
        if volume:
            conditions.append(f"volume = ${param_idx}")
            params.append(volume)
            param_idx += 1

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
        SELECT id, trend, volatility, volume, sentiment, description
        FROM market_condition_taxonomy
        {where_clause}
        ORDER BY trend, volatility, volume
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        items = []
        for row in rows:
            items.append({
                "condition_id": str(row["id"]),
                "trend": row["trend"],
                "volatility": row["volatility"],
                "volume": row["volume"],
                "sentiment": row["sentiment"],
                "description": row["description"],
            })

        return {"items": items, "count": len(items)}

    # ── Strategy Recommendation ──────────────────────────────────────────

    async def recommend_strategies(
        self,
        trend: str,
        volatility: str,
        volume: str,
        instrument: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Recommend strategies for given market conditions based on historical performance."""
        self._ensure_pool()

        # Find matching market condition
        instrument_filter = ""
        params: List[Any] = [trend, volatility, volume]
        param_idx = 4

        if instrument:
            instrument_filter = f"AND scp.instrument = ${param_idx}"
            params.append(instrument)
            param_idx += 1

        params.append(limit)

        query = f"""
        SELECT
            ss.id AS spec_id,
            ss.name AS spec_name,
            ss.indicators,
            ss.description,
            mct.trend,
            mct.volatility,
            mct.volume,
            mct.sentiment,
            mct.description AS condition_description,
            scp.sample_size,
            scp.win_rate,
            scp.avg_return,
            scp.sharpe_ratio,
            scp.max_drawdown,
            scp.instrument
        FROM strategy_condition_performance scp
        JOIN strategy_specs ss ON scp.strategy_spec_id = ss.id
        JOIN market_condition_taxonomy mct ON scp.condition_id = mct.id
        WHERE mct.trend = $1
          AND mct.volatility = $2
          AND mct.volume = $3
          AND scp.sample_size >= 10
          {instrument_filter}
        ORDER BY scp.sharpe_ratio DESC NULLS LAST
        LIMIT ${param_idx}
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        recommendations = []
        for row in rows:
            indicators = row["indicators"]
            if isinstance(indicators, str):
                indicators = json.loads(indicators)

            recommendations.append({
                "spec_id": str(row["spec_id"]),
                "spec_name": row["spec_name"],
                "description": row["description"],
                "indicators": indicators,
                "instrument": row["instrument"],
                "performance": {
                    "sample_size": row["sample_size"],
                    "win_rate": float(row["win_rate"]) if row["win_rate"] else None,
                    "avg_return": float(row["avg_return"]) if row["avg_return"] else None,
                    "sharpe_ratio": float(row["sharpe_ratio"]) if row["sharpe_ratio"] else None,
                    "max_drawdown": float(row["max_drawdown"]) if row["max_drawdown"] else None,
                },
            })

        condition_desc = None
        if rows:
            condition_desc = rows[0]["condition_description"]

        return {
            "market_condition": {
                "trend": trend,
                "volatility": volatility,
                "volume": volume,
                "description": condition_desc,
            },
            "recommendations": recommendations,
            "count": len(recommendations),
        }

    # ── Composite Strategies ─────────────────────────────────────────────

    async def create_composite_strategy(
        self,
        name: str,
        description: str,
        component_spec_ids: List[str],
        weights: Optional[List[float]] = None,
        combination_method: str = "weighted_average",
        min_agreement: float = 0.5,
    ) -> Dict[str, Any]:
        """Create a composite strategy from multiple strategy specs."""
        self._ensure_pool()

        if weights and len(weights) != len(component_spec_ids):
            return {
                "created": False,
                "error": "weights length must match component_spec_ids length",
            }

        if not weights:
            weights = [1.0 / len(component_spec_ids)] * len(component_spec_ids)

        async with self.pool.acquire() as conn:
            # Check for duplicate name
            existing = await conn.fetchrow(
                "SELECT id FROM composite_strategies WHERE name = $1", name
            )
            if existing:
                return {
                    "composite_id": str(existing["id"]),
                    "created": False,
                    "error": f"Composite strategy '{name}' already exists",
                }

            # Create composite in transaction
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO composite_strategies
                        (name, description, combination_method, min_agreement)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id
                    """,
                    name,
                    description,
                    combination_method,
                    min_agreement,
                )
                composite_id = row["id"]

                for i, spec_id in enumerate(component_spec_ids):
                    await conn.execute(
                        """
                        INSERT INTO composite_strategy_components
                            (composite_id, strategy_spec_id, weight)
                        VALUES ($1, $2::uuid, $3)
                        """,
                        composite_id,
                        spec_id,
                        weights[i],
                    )

        return {
            "composite_id": str(composite_id),
            "created": True,
            "components_count": len(component_spec_ids),
        }

    async def get_composite_strategy(
        self, composite_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a composite strategy with its components and performance."""
        self._ensure_pool()

        query = """
        SELECT
            cs.id, cs.name, cs.description, cs.combination_method,
            cs.min_agreement, cs.is_active, cs.created_at
        FROM composite_strategies cs
        WHERE cs.id = $1::uuid
        """

        components_query = """
        SELECT
            csc.strategy_spec_id,
            ss.name AS spec_name,
            ss.indicators,
            csc.weight,
            csc.role
        FROM composite_strategy_components csc
        JOIN strategy_specs ss ON csc.strategy_spec_id = ss.id
        WHERE csc.composite_id = $1::uuid
        ORDER BY csc.weight DESC
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, composite_id)
            if not row:
                return None

            comp_rows = await conn.fetch(components_query, composite_id)

        components = []
        for cr in comp_rows:
            indicators = cr["indicators"]
            if isinstance(indicators, str):
                indicators = json.loads(indicators)
            components.append({
                "spec_id": str(cr["strategy_spec_id"]),
                "spec_name": cr["spec_name"],
                "indicators": indicators,
                "weight": float(cr["weight"]),
                "role": cr["role"],
            })

        return {
            "composite_id": str(row["id"]),
            "name": row["name"],
            "description": row["description"],
            "combination_method": row["combination_method"],
            "min_agreement": float(row["min_agreement"]),
            "is_active": row["is_active"],
            "components": components,
        }

    async def list_composite_strategies(
        self, active_only: bool = True, limit: int = 20
    ) -> Dict[str, Any]:
        """List composite strategies."""
        self._ensure_pool()

        active_filter = "WHERE cs.is_active = TRUE" if active_only else ""

        query = f"""
        SELECT
            cs.id, cs.name, cs.description, cs.combination_method,
            cs.is_active,
            COUNT(csc.id) AS components_count
        FROM composite_strategies cs
        LEFT JOIN composite_strategy_components csc ON cs.id = csc.composite_id
        {active_filter}
        GROUP BY cs.id, cs.name, cs.description, cs.combination_method, cs.is_active
        ORDER BY cs.created_at DESC
        LIMIT $1
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, limit)

        items = []
        for row in rows:
            items.append({
                "composite_id": str(row["id"]),
                "name": row["name"],
                "description": row["description"],
                "combination_method": row["combination_method"],
                "is_active": row["is_active"],
                "components_count": row["components_count"],
            })

        return {"items": items, "count": len(items)}

    # ── Performance Attribution ──────────────────────────────────────────

    async def get_performance_attribution(
        self, composite_id: str, instrument: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get performance attribution for a composite strategy's components."""
        self._ensure_pool()

        instrument_filter = ""
        params: List[Any] = [composite_id]
        if instrument:
            instrument_filter = "AND cpa.instrument = $2"
            params.append(instrument)

        query = f"""
        SELECT
            ss.name AS component_name,
            cpa.component_spec_id,
            cpa.instrument,
            SUM(cpa.signals_generated) AS total_signals,
            SUM(cpa.signals_agreed) AS total_agreed,
            SUM(cpa.contribution_pnl) AS total_pnl,
            AVG(cpa.contribution_pct) AS avg_contribution_pct,
            AVG(cpa.accuracy) AS avg_accuracy
        FROM composite_performance_attribution cpa
        JOIN strategy_specs ss ON cpa.component_spec_id = ss.id
        WHERE cpa.composite_id = $1::uuid {instrument_filter}
        GROUP BY ss.name, cpa.component_spec_id, cpa.instrument
        ORDER BY total_pnl DESC
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        attributions = []
        for row in rows:
            attributions.append({
                "component_name": row["component_name"],
                "component_spec_id": str(row["component_spec_id"]),
                "instrument": row["instrument"],
                "total_signals": row["total_signals"],
                "total_agreed": row["total_agreed"],
                "total_pnl": float(row["total_pnl"]) if row["total_pnl"] else 0.0,
                "avg_contribution_pct": float(row["avg_contribution_pct"]) if row["avg_contribution_pct"] else None,
                "avg_accuracy": float(row["avg_accuracy"]) if row["avg_accuracy"] else None,
            })

        return {
            "composite_id": composite_id,
            "attributions": attributions,
            "count": len(attributions),
        }

    # ── Knowledge Graph Exploration ──────────────────────────────────────

    async def explore_strategy_graph(
        self, spec_id: str
    ) -> Dict[str, Any]:
        """Explore the knowledge graph around a strategy spec: indicators, conditions, tags, composites."""
        self._ensure_pool()

        spec_query = """
        SELECT id, name, indicators, entry_conditions, exit_conditions, description
        FROM strategy_specs WHERE id = $1::uuid
        """

        tags_query = """
        SELECT tag FROM strategy_tags WHERE strategy_spec_id = $1::uuid
        """

        composites_query = """
        SELECT cs.id, cs.name, csc.weight, csc.role
        FROM composite_strategy_components csc
        JOIN composite_strategies cs ON csc.composite_id = cs.id
        WHERE csc.strategy_spec_id = $1::uuid AND cs.is_active = TRUE
        """

        conditions_query = """
        SELECT
            mct.trend, mct.volatility, mct.volume, mct.sentiment,
            scp.sharpe_ratio, scp.win_rate, scp.sample_size, scp.instrument
        FROM strategy_condition_performance scp
        JOIN market_condition_taxonomy mct ON scp.condition_id = mct.id
        WHERE scp.strategy_spec_id = $1::uuid AND scp.sample_size >= 5
        ORDER BY scp.sharpe_ratio DESC NULLS LAST
        LIMIT 10
        """

        async with self.pool.acquire() as conn:
            spec = await conn.fetchrow(spec_query, spec_id)
            if not spec:
                return None

            tags = await conn.fetch(tags_query, spec_id)
            composites = await conn.fetch(composites_query, spec_id)
            conditions = await conn.fetch(conditions_query, spec_id)

        indicators = spec["indicators"]
        if isinstance(indicators, str):
            indicators = json.loads(indicators)

        entry_conditions = spec["entry_conditions"]
        if isinstance(entry_conditions, str):
            entry_conditions = json.loads(entry_conditions)

        exit_conditions = spec["exit_conditions"]
        if isinstance(exit_conditions, str):
            exit_conditions = json.loads(exit_conditions)

        return {
            "spec_id": str(spec["id"]),
            "name": spec["name"],
            "description": spec["description"],
            "indicators": indicators,
            "entry_conditions": entry_conditions,
            "exit_conditions": exit_conditions,
            "tags": [t["tag"] for t in tags],
            "composites": [
                {
                    "composite_id": str(c["id"]),
                    "composite_name": c["name"],
                    "weight": float(c["weight"]),
                    "role": c["role"],
                }
                for c in composites
            ],
            "best_conditions": [
                {
                    "trend": c["trend"],
                    "volatility": c["volatility"],
                    "volume": c["volume"],
                    "sentiment": c["sentiment"],
                    "sharpe_ratio": float(c["sharpe_ratio"]) if c["sharpe_ratio"] else None,
                    "win_rate": float(c["win_rate"]) if c["win_rate"] else None,
                    "sample_size": c["sample_size"],
                    "instrument": c["instrument"],
                }
                for c in conditions
            ],
        }

    async def find_similar_strategies(
        self, spec_id: str, limit: int = 10
    ) -> Dict[str, Any]:
        """Find strategies similar to the given one based on shared indicators and tags."""
        self._ensure_pool()

        query = """
        WITH target_tags AS (
            SELECT tag FROM strategy_tags WHERE strategy_spec_id = $1::uuid
        ),
        target_indicators AS (
            SELECT jsonb_array_elements(indicators)->>'type' AS ind_type
            FROM strategy_specs WHERE id = $1::uuid
        ),
        candidate_scores AS (
            SELECT
                ss.id AS spec_id,
                ss.name,
                ss.description,
                ss.indicators,
                -- Tag overlap score
                COALESCE(
                    (SELECT COUNT(*) FROM strategy_tags st
                     WHERE st.strategy_spec_id = ss.id
                       AND st.tag IN (SELECT tag FROM target_tags)),
                    0
                ) AS tag_overlap,
                -- Indicator overlap score
                COALESCE(
                    (SELECT COUNT(*) FROM (
                        SELECT jsonb_array_elements(ss.indicators)->>'type' AS ind_type
                        INTERSECT
                        SELECT ind_type FROM target_indicators
                    ) overlap),
                    0
                ) AS indicator_overlap
            FROM strategy_specs ss
            WHERE ss.id != $1::uuid AND ss.is_active = TRUE
        )
        SELECT spec_id, name, description, indicators,
               tag_overlap, indicator_overlap,
               (tag_overlap + indicator_overlap) AS similarity_score
        FROM candidate_scores
        WHERE (tag_overlap + indicator_overlap) > 0
        ORDER BY similarity_score DESC
        LIMIT $2
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, spec_id, limit)

        items = []
        for row in rows:
            indicators = row["indicators"]
            if isinstance(indicators, str):
                indicators = json.loads(indicators)
            items.append({
                "spec_id": str(row["spec_id"]),
                "name": row["name"],
                "description": row["description"],
                "indicators": indicators,
                "tag_overlap": row["tag_overlap"],
                "indicator_overlap": row["indicator_overlap"],
                "similarity_score": row["similarity_score"],
            })

        return {"source_spec_id": spec_id, "similar": items, "count": len(items)}
