"""Opportunity Scoring and Discovery API endpoints and schemas."""

OPPORTUNITIES_TAGS = [
    {
        "name": "Opportunities",
        "description": "AI-scored trading opportunities with confluence analysis",
    },
]

OPPORTUNITIES_SCHEMAS = {
    "Opportunity": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "instrument": {"type": "string", "example": "ETH/USD"},
            "direction": {"type": "string", "enum": ["BUY", "SELL"]},
            "score": {
                "type": "number",
                "format": "double",
                "minimum": 0,
                "maximum": 100,
                "description": "Composite opportunity score (0-100)",
                "example": 82.5,
            },
            "tier": {
                "type": "string",
                "enum": ["S", "A", "B", "C", "D"],
                "description": "Score tier (S=90+, A=80+, B=70+, C=60+, D=below 60)",
                "example": "A",
            },
            "confluence_factors": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/ConfluenceFactor"},
            },
            "entry_zone": {
                "type": "object",
                "properties": {
                    "low": {"type": "number", "format": "double"},
                    "high": {"type": "number", "format": "double"},
                },
                "example": {"low": 3200.00, "high": 3250.00},
            },
            "stop_loss": {"type": "number", "format": "double", "example": 3100.00},
            "targets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "price": {"type": "number", "format": "double"},
                        "label": {"type": "string"},
                    },
                },
                "example": [
                    {"price": 3400.00, "label": "TP1"},
                    {"price": 3600.00, "label": "TP2"},
                ],
            },
            "risk_reward_ratio": {"type": "number", "format": "double", "example": 2.5},
            "timeframe": {"type": "string", "example": "4h"},
            "expires_at": {"type": "string", "format": "date-time"},
            "created_at": {"type": "string", "format": "date-time"},
            "status": {
                "type": "string",
                "enum": ["active", "expired", "triggered", "invalidated"],
            },
        },
        "required": ["id", "instrument", "direction", "score", "tier"],
    },
    "ConfluenceFactor": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "example": "RSI Oversold"},
            "category": {
                "type": "string",
                "enum": [
                    "technical",
                    "sentiment",
                    "fundamental",
                    "flow",
                    "correlation",
                ],
            },
            "weight": {"type": "number", "format": "double", "example": 0.15},
            "signal": {
                "type": "string",
                "enum": ["bullish", "bearish", "neutral"],
            },
            "value": {"type": "number", "format": "double", "example": 28.5},
            "description": {
                "type": "string",
                "example": "RSI at 28.5, below oversold threshold of 30",
            },
        },
    },
    "OpportunityScan": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "instruments_scanned": {"type": "integer", "example": 50},
            "opportunities_found": {"type": "integer", "example": 7},
            "scan_duration_ms": {"type": "integer", "example": 3200},
            "created_at": {"type": "string", "format": "date-time"},
        },
    },
}

OPPORTUNITIES_PATHS = {
    "/api/v1/opportunities": {
        "get": {
            "summary": "List trading opportunities",
            "description": (
                "Get AI-scored trading opportunities sorted by score. "
                "Each opportunity includes confluence factors and risk/reward analysis."
            ),
            "operationId": "listOpportunities",
            "tags": ["Opportunities"],
            "parameters": [
                {
                    "name": "instrument",
                    "in": "query",
                    "schema": {"type": "string"},
                },
                {
                    "name": "direction",
                    "in": "query",
                    "schema": {"type": "string", "enum": ["BUY", "SELL"]},
                },
                {
                    "name": "min_score",
                    "in": "query",
                    "schema": {"type": "number", "minimum": 0, "maximum": 100},
                    "description": "Minimum opportunity score",
                },
                {
                    "name": "tier",
                    "in": "query",
                    "schema": {"type": "string", "enum": ["S", "A", "B", "C"]},
                    "description": "Minimum tier filter",
                },
                {
                    "name": "status",
                    "in": "query",
                    "schema": {
                        "type": "string",
                        "enum": ["active", "expired", "triggered", "invalidated"],
                        "default": "active",
                    },
                },
                {
                    "name": "timeframe",
                    "in": "query",
                    "schema": {"type": "string"},
                },
                {
                    "name": "limit",
                    "in": "query",
                    "schema": {"type": "integer", "default": 20},
                },
                {
                    "name": "offset",
                    "in": "query",
                    "schema": {"type": "integer", "default": 0},
                },
            ],
            "responses": {
                "200": {
                    "description": "Paginated opportunities sorted by score descending",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/CollectionResponse"
                            },
                            "example": {
                                "data": [
                                    {
                                        "type": "opportunity",
                                        "id": "opp_abc123",
                                        "attributes": {
                                            "instrument": "ETH/USD",
                                            "direction": "BUY",
                                            "score": 82.5,
                                            "tier": "A",
                                            "risk_reward_ratio": 2.5,
                                            "confluence_factors": [
                                                {
                                                    "name": "RSI Oversold",
                                                    "signal": "bullish",
                                                },
                                                {
                                                    "name": "MACD Crossover",
                                                    "signal": "bullish",
                                                },
                                            ],
                                        },
                                    }
                                ],
                                "meta": {"total": 7, "limit": 20, "offset": 0},
                            },
                        },
                    },
                },
            },
        },
    },
    "/api/v1/opportunities/{opportunity_id}": {
        "get": {
            "summary": "Get opportunity details",
            "description": "Get full details for a specific opportunity including all confluence factors.",
            "operationId": "getOpportunity",
            "tags": ["Opportunities"],
            "parameters": [
                {
                    "name": "opportunity_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
            ],
            "responses": {
                "200": {
                    "description": "Opportunity details",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Opportunity"},
                        },
                    },
                },
                "404": {
                    "description": "Opportunity not found",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/opportunities/scan": {
        "post": {
            "summary": "Trigger opportunity scan",
            "description": "Manually trigger an opportunity scan across specified instruments or watchlist.",
            "operationId": "triggerOpportunityScan",
            "tags": ["Opportunities"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "instruments": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Instruments to scan (empty = scan watchlist)",
                                    "example": ["BTC/USD", "ETH/USD", "SOL/USD"],
                                },
                                "timeframes": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "example": ["1h", "4h", "1d"],
                                },
                                "min_score": {
                                    "type": "number",
                                    "description": "Only return opportunities above this score",
                                    "example": 60,
                                },
                            },
                        },
                    },
                },
            },
            "responses": {
                "202": {
                    "description": "Scan queued",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/OpportunityScan"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/opportunities/history": {
        "get": {
            "summary": "Get opportunity performance history",
            "description": "Track how past opportunities performed after being identified.",
            "operationId": "getOpportunityHistory",
            "tags": ["Opportunities"],
            "parameters": [
                {"name": "instrument", "in": "query", "schema": {"type": "string"}},
                {
                    "name": "period",
                    "in": "query",
                    "schema": {
                        "type": "string",
                        "enum": ["7d", "30d", "90d"],
                        "default": "30d",
                    },
                },
                {"name": "min_score", "in": "query", "schema": {"type": "number"}},
            ],
            "responses": {
                "200": {
                    "description": "Historical opportunity performance",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "total_opportunities": {"type": "integer"},
                                    "hit_rate": {"type": "number", "format": "double"},
                                    "avg_return_pct": {
                                        "type": "number",
                                        "format": "double",
                                    },
                                    "by_tier": {
                                        "type": "object",
                                        "additionalProperties": {
                                            "type": "object",
                                            "properties": {
                                                "count": {"type": "integer"},
                                                "hit_rate": {"type": "number"},
                                                "avg_return_pct": {"type": "number"},
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}
