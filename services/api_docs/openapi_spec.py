"""
Unified OpenAPI 3.0 specification for all TradeStream REST APIs.

Aggregates endpoint definitions from all microservices into a single
spec that can be served via Swagger UI or exported as JSON/YAML.
"""

OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "TradeStream API",
        "description": (
            "Unified API documentation for the TradeStream platform. "
            "TradeStream is an AI-powered trading system that provides strategy "
            "derivation, backtesting, portfolio management, market data, "
            "paper trading, and agent monitoring capabilities."
        ),
        "version": "1.0.0",
        "contact": {"name": "TradeStream"},
    },
    "servers": [
        {
            "url": "http://localhost:8080",
            "description": "Local development",
        },
    ],
    "tags": [
        {
            "name": "Portfolio",
            "description": "Portfolio state and balance management",
        },
        {
            "name": "Positions",
            "description": "Open position tracking",
        },
        {
            "name": "Risk",
            "description": "Risk metrics and trade validation",
        },
        {
            "name": "Specs",
            "description": "Strategy specification CRUD",
        },
        {
            "name": "Implementations",
            "description": "Strategy implementation management and evaluation",
        },
        {
            "name": "Instruments",
            "description": "Market instruments, candles, and prices",
        },
        {
            "name": "Decisions",
            "description": "Agent decision tracking",
        },
        {
            "name": "Analytics",
            "description": "Performance analytics, patterns, and similarity search",
        },
        {
            "name": "Events",
            "description": "Real-time agent event streaming",
        },
        {
            "name": "Dashboard",
            "description": "Agent dashboard and monitoring",
        },
        {
            "name": "Strategies",
            "description": "Strategy monitoring and visualization",
        },
        {
            "name": "Paper Trading",
            "description": "Simulated trade execution and P&L tracking",
        },
        {
            "name": "Portfolio State",
            "description": "Portfolio state awareness for decision agents",
        },
        {
            "name": "Health",
            "description": "Service health and readiness checks",
        },
    ],
    "components": {
        "securitySchemes": {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for authentication",
            },
        },
        "schemas": {
            # --- Standard envelope schemas ---
            "SuccessResponse": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "description": "Resource type identifier",
                            },
                            "id": {
                                "type": "string",
                                "description": "Resource ID (when applicable)",
                            },
                            "attributes": {
                                "type": "object",
                                "description": "Resource attributes",
                            },
                        },
                        "required": ["type", "attributes"],
                    },
                },
                "required": ["data"],
            },
            "CollectionResponse": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "id": {"type": "string"},
                                "attributes": {"type": "object"},
                            },
                            "required": ["type", "attributes"],
                        },
                    },
                    "meta": {
                        "$ref": "#/components/schemas/PaginationMeta",
                    },
                },
                "required": ["data", "meta"],
            },
            "PaginationMeta": {
                "type": "object",
                "properties": {
                    "total": {
                        "type": "integer",
                        "description": "Total number of items",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max items per page",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of items skipped",
                    },
                },
                "required": ["total", "limit", "offset"],
            },
            "ErrorResponse": {
                "type": "object",
                "properties": {
                    "error": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Machine-readable error code",
                                "example": "NOT_FOUND",
                            },
                            "message": {
                                "type": "string",
                                "description": "Human-readable error message",
                            },
                            "details": {
                                "type": "array",
                                "items": {"type": "object"},
                                "description": "Additional error details",
                            },
                        },
                        "required": ["code", "message"],
                    },
                },
                "required": ["error"],
            },
            "HealthResponse": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["healthy", "degraded"],
                        "example": "healthy",
                    },
                    "service": {
                        "type": "string",
                        "example": "portfolio-api",
                    },
                },
                "required": ["status", "service"],
            },
            "ReadyResponse": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["ready", "degraded"],
                    },
                    "service": {"type": "string"},
                    "dependencies": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["status", "service"],
            },
            # --- Portfolio API schemas ---
            "PortfolioState": {
                "type": "object",
                "properties": {
                    "positions": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Position"},
                    },
                    "position_count": {"type": "integer"},
                    "total_unrealized_pnl": {
                        "type": "number",
                        "format": "double",
                    },
                    "trade_stats": {
                        "$ref": "#/components/schemas/TradeStats",
                    },
                },
            },
            "Position": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "example": "BTC/USD"},
                    "quantity": {"type": "number", "format": "double"},
                    "avg_entry_price": {"type": "number", "format": "double"},
                    "unrealized_pnl": {"type": "number", "format": "double"},
                    "updated_at": {"type": "string", "format": "date-time"},
                },
            },
            "TradeStats": {
                "type": "object",
                "properties": {
                    "total_trades": {"type": "integer"},
                    "winning_trades": {"type": "integer"},
                    "losing_trades": {"type": "integer"},
                    "total_realized_pnl": {"type": "number", "format": "double"},
                },
            },
            "Balance": {
                "type": "object",
                "properties": {
                    "total_realized_pnl": {"type": "number", "format": "double"},
                    "total_unrealized_pnl": {"type": "number", "format": "double"},
                    "total_equity": {"type": "number", "format": "double"},
                },
            },
            "RiskMetrics": {
                "type": "object",
                "properties": {
                    "total_exposure": {"type": "number", "format": "double"},
                    "position_count": {"type": "integer"},
                    "concentration": {
                        "type": "object",
                        "additionalProperties": {"type": "number"},
                        "description": "Per-instrument concentration ratios",
                    },
                },
            },
            "TradeValidationRequest": {
                "type": "object",
                "properties": {
                    "instrument": {
                        "type": "string",
                        "description": "Trading instrument symbol",
                        "example": "BTC/USD",
                    },
                    "side": {
                        "type": "string",
                        "enum": ["BUY", "SELL"],
                        "description": "Trade side",
                    },
                    "size": {
                        "type": "number",
                        "format": "double",
                        "exclusiveMinimum": 0,
                        "description": "Trade size",
                    },
                },
                "required": ["instrument", "side", "size"],
            },
            "TradeValidationResult": {
                "type": "object",
                "properties": {
                    "valid": {"type": "boolean"},
                    "errors": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            # --- Strategy API schemas ---
            "StrategySpecCreate": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Unique spec name"},
                    "indicators": {
                        "type": "object",
                        "description": "Indicator configurations",
                    },
                    "entry_conditions": {
                        "type": "object",
                        "description": "Entry rule definitions",
                    },
                    "exit_conditions": {
                        "type": "object",
                        "description": "Exit rule definitions",
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Parameter definitions with ranges",
                    },
                    "description": {
                        "type": "string",
                        "description": "Human-readable description",
                    },
                },
                "required": [
                    "name",
                    "indicators",
                    "entry_conditions",
                    "exit_conditions",
                    "parameters",
                    "description",
                ],
            },
            "StrategySpecUpdate": {
                "type": "object",
                "properties": {
                    "indicators": {"type": "object"},
                    "entry_conditions": {"type": "object"},
                    "exit_conditions": {"type": "object"},
                    "parameters": {"type": "object"},
                    "description": {"type": "string"},
                },
            },
            "StrategySpec": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "format": "uuid"},
                    "name": {"type": "string"},
                    "indicators": {"type": "object"},
                    "entry_conditions": {"type": "object"},
                    "exit_conditions": {"type": "object"},
                    "parameters": {"type": "object"},
                    "description": {"type": "string"},
                    "source": {"type": "string"},
                    "created_at": {"type": "string", "format": "date-time"},
                },
            },
            "StrategyImplementation": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "format": "uuid"},
                    "spec_id": {"type": "string", "format": "uuid"},
                    "parameters": {"type": "object"},
                    "status": {
                        "type": "string",
                        "enum": ["PENDING", "ACTIVE", "INACTIVE"],
                    },
                    "optimization_method": {"type": "string"},
                    "backtest_metrics": {"type": "object"},
                    "paper_metrics": {"type": "object"},
                    "live_metrics": {"type": "object"},
                    "created_at": {"type": "string", "format": "date-time"},
                },
            },
            "EvaluateRequest": {
                "type": "object",
                "properties": {
                    "instrument": {
                        "type": "string",
                        "description": "Trading instrument symbol",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Backtest start date (ISO format)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Backtest end date (ISO format)",
                    },
                },
                "required": ["instrument", "start_date", "end_date"],
            },
            "BacktestResult": {
                "type": "object",
                "properties": {
                    "implementation_id": {"type": "string", "format": "uuid"},
                    "instrument": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "status": {"type": "string", "example": "SUBMITTED"},
                },
            },
            "Signal": {
                "type": "object",
                "properties": {
                    "signal_id": {"type": "string", "format": "uuid"},
                    "symbol": {"type": "string"},
                    "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
                    "confidence": {"type": "number", "format": "double"},
                    "created_at": {"type": "string", "format": "date-time"},
                },
            },
            # --- Market Data API schemas ---
            "Instrument": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "example": "BTC/USD"},
                },
            },
            "Candle": {
                "type": "object",
                "properties": {
                    "timestamp": {"type": "string", "format": "date-time"},
                    "open": {"type": "number", "format": "double"},
                    "high": {"type": "number", "format": "double"},
                    "low": {"type": "number", "format": "double"},
                    "close": {"type": "number", "format": "double"},
                    "volume": {"type": "number", "format": "double"},
                },
            },
            "Price": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "price": {"type": "number", "format": "double"},
                    "timestamp": {"type": "string", "format": "date-time"},
                },
            },
            "OrderBook": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "depth": {"type": "integer"},
                    "bids": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                    "asks": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                    "message": {"type": "string"},
                },
            },
            # --- Learning API schemas ---
            "DecisionCreate": {
                "type": "object",
                "properties": {
                    "signal_id": {"type": "string", "description": "Associated signal UUID"},
                    "agent_name": {"type": "string", "description": "Name of the deciding agent"},
                    "decision_type": {"type": "string", "description": "Decision category"},
                    "score": {
                        "type": "number",
                        "format": "double",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "Decision score (0-1)",
                    },
                    "tier": {"type": "string", "description": "Decision tier"},
                    "reasoning": {"type": "string", "description": "Decision reasoning text"},
                    "tool_calls": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Tool calls made",
                    },
                    "model_used": {"type": "string", "description": "LLM model used"},
                    "latency_ms": {"type": "integer", "description": "Processing latency in ms"},
                    "tokens_used": {"type": "integer", "description": "Token count"},
                },
                "required": [
                    "signal_id",
                    "agent_name",
                    "decision_type",
                    "score",
                    "tier",
                    "reasoning",
                ],
            },
            "Decision": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "format": "uuid"},
                    "signal_id": {"type": "string"},
                    "agent_name": {"type": "string"},
                    "decision_type": {"type": "string"},
                    "score": {"type": "number", "format": "double"},
                    "tier": {"type": "string"},
                    "reasoning": {"type": "string"},
                    "tool_calls": {"type": "object"},
                    "model_used": {"type": "string"},
                    "latency_ms": {"type": "integer"},
                    "tokens_used": {"type": "integer"},
                    "success": {"type": "boolean"},
                    "error_message": {"type": "string"},
                    "created_at": {"type": "string", "format": "date-time"},
                },
            },
            "OutcomeUpdate": {
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "description": "Whether the decision was successful",
                    },
                    "error_message": {
                        "type": "string",
                        "description": "Error message if failed",
                    },
                },
                "required": ["success"],
            },
            "MarketContext": {
                "type": "object",
                "properties": {
                    "instrument": {"type": "string", "description": "Trading instrument"},
                    "price": {"type": "number", "format": "double", "description": "Current price"},
                    "volatility": {"type": "number", "format": "double"},
                    "volume": {"type": "number", "format": "double"},
                },
                "required": ["instrument", "price"],
            },
            "Pattern": {
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string"},
                    "tier": {"type": "string"},
                    "count": {"type": "integer"},
                    "avg_score": {"type": "number", "format": "double"},
                    "successes": {"type": "integer"},
                    "failures": {"type": "integer"},
                },
            },
            "PerformanceMetrics": {
                "type": "object",
                "properties": {
                    "total_decisions": {"type": "integer"},
                    "avg_score": {"type": "number", "format": "double"},
                    "avg_latency_ms": {"type": "number", "format": "double"},
                    "successes": {"type": "integer"},
                    "failures": {"type": "integer"},
                    "unique_agents": {"type": "integer"},
                    "period": {"type": "string"},
                },
            },
            # --- Agent Gateway schemas ---
            "AgentEvent": {
                "type": "object",
                "properties": {
                    "event_type": {
                        "type": "string",
                        "enum": ["signal", "reasoning", "tool_call", "decision"],
                    },
                    "id": {"type": "string"},
                    "signal_id": {"type": "string"},
                    "agent_name": {"type": "string"},
                    "decision_type": {"type": "string"},
                    "score": {"type": "number", "format": "double"},
                    "tier": {"type": "string"},
                    "reasoning": {"type": "string"},
                    "tool_calls": {"type": "string"},
                    "model_used": {"type": "string"},
                    "latency_ms": {"type": "integer"},
                    "tokens_used": {"type": "integer"},
                    "success": {"type": "boolean"},
                    "error_message": {"type": "string"},
                    "created_at": {"type": "string", "format": "date-time"},
                },
            },
            "DashboardSummary": {
                "type": "object",
                "properties": {
                    "active_agents": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                    "stats_24h": {"type": "object"},
                    "tier_distribution": {
                        "type": "object",
                        "additionalProperties": {"type": "integer"},
                    },
                    "recent_signals": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/AgentEvent"},
                    },
                },
            },
            # --- Strategy Monitor API schemas ---
            "MonitoredStrategy": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "symbol": {"type": "string"},
                    "strategy_type": {"type": "string"},
                    "score": {"type": "number", "format": "double"},
                    "parameters": {"type": "object"},
                    "created_at": {"type": "string", "format": "date-time"},
                },
            },
            "StrategyMetrics": {
                "type": "object",
                "properties": {
                    "total_strategies": {"type": "integer"},
                    "avg_score": {"type": "number", "format": "double"},
                    "by_type": {
                        "type": "object",
                        "additionalProperties": {"type": "integer"},
                    },
                    "by_symbol": {
                        "type": "object",
                        "additionalProperties": {"type": "integer"},
                    },
                },
            },
            # --- Paper Trading schemas ---
            "PaperTradeRequest": {
                "type": "object",
                "properties": {
                    "signal_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "UUID of the signal to trade on",
                    },
                    "quantity": {
                        "type": "number",
                        "format": "double",
                        "exclusiveMinimum": 0,
                        "description": "Amount to trade",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Optional reasoning for the trade decision",
                    },
                },
                "required": ["signal_id", "quantity"],
            },
            "PaperTrade": {
                "type": "object",
                "properties": {
                    "trade_id": {"type": "string", "format": "uuid"},
                    "signal_id": {"type": "string"},
                    "symbol": {"type": "string"},
                    "side": {"type": "string", "enum": ["BUY", "SELL"]},
                    "entry_price": {"type": "number", "format": "double"},
                    "quantity": {"type": "number", "format": "double"},
                    "status": {"type": "string", "enum": ["OPEN", "CLOSED"]},
                    "pnl": {"type": "number", "format": "double"},
                    "created_at": {"type": "string", "format": "date-time"},
                },
            },
            "PaperPortfolio": {
                "type": "object",
                "properties": {
                    "positions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "symbol": {"type": "string"},
                                "quantity": {"type": "number", "format": "double"},
                                "avg_entry_price": {"type": "number", "format": "double"},
                                "current_price": {"type": "number", "format": "double"},
                                "unrealized_pnl": {"type": "number", "format": "double"},
                            },
                        },
                    },
                },
            },
            "PnlSummary": {
                "type": "object",
                "properties": {
                    "total_realized_pnl": {"type": "number", "format": "double"},
                    "total_unrealized_pnl": {"type": "number", "format": "double"},
                    "total_trades": {"type": "integer"},
                    "winning_trades": {"type": "integer"},
                    "losing_trades": {"type": "integer"},
                    "win_rate": {"type": "number", "format": "double"},
                },
            },
            # --- Portfolio State schemas ---
            "FullPortfolioState": {
                "type": "object",
                "properties": {
                    "balance": {
                        "type": "object",
                        "properties": {
                            "total_equity": {"type": "number", "format": "double"},
                            "available_cash": {"type": "number", "format": "double"},
                            "buying_power": {"type": "number", "format": "double"},
                            "margin_used": {"type": "number", "format": "double"},
                            "margin_available": {"type": "number", "format": "double"},
                            "unrealized_pnl": {"type": "number", "format": "double"},
                            "realized_pnl_today": {"type": "number", "format": "double"},
                        },
                    },
                    "positions": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/DetailedPosition"},
                    },
                    "risk_metrics": {
                        "$ref": "#/components/schemas/FullRiskMetrics",
                    },
                    "recent_trades": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                    "as_of": {"type": "string", "format": "date-time"},
                },
            },
            "DetailedPosition": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "side": {"type": "string", "enum": ["LONG", "SHORT"]},
                    "quantity": {"type": "number", "format": "double"},
                    "entry_price": {"type": "number", "format": "double"},
                    "current_price": {"type": "number", "format": "double"},
                    "unrealized_pnl": {"type": "number", "format": "double"},
                    "unrealized_pnl_percent": {"type": "number", "format": "double"},
                    "opened_at": {"type": "string"},
                },
            },
            "FullRiskMetrics": {
                "type": "object",
                "properties": {
                    "portfolio_heat": {"type": "number", "format": "double"},
                    "max_position_pct": {"type": "number", "format": "double"},
                    "max_position_symbol": {"type": "string"},
                    "num_open_positions": {"type": "integer"},
                    "sector_exposure": {"type": "object"},
                    "daily_drawdown": {"type": "number", "format": "double"},
                },
            },
            "DecisionValidateRequest": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["BUY", "SELL"]},
                    "symbol": {"type": "string"},
                    "quantity": {"type": "number", "format": "double"},
                    "price": {"type": "number", "format": "double"},
                    "max_position_pct": {
                        "type": "number",
                        "format": "double",
                        "default": 0.02,
                    },
                    "max_portfolio_heat": {
                        "type": "number",
                        "format": "double",
                        "default": 0.50,
                    },
                },
                "required": ["action", "symbol", "quantity", "price"],
            },
        },
    },
    "security": [{"ApiKeyAuth": []}],
    "paths": {
        # ===================================================================
        # Portfolio API — /api/v1/portfolio
        # ===================================================================
        "/api/v1/portfolio/health": {
            "get": {
                "summary": "Portfolio API health check",
                "operationId": "portfolioHealth",
                "tags": ["Health"],
                "security": [],
                "responses": {
                    "200": {
                        "description": "Service is healthy",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/portfolio/ready": {
            "get": {
                "summary": "Portfolio API readiness check",
                "operationId": "portfolioReady",
                "tags": ["Health"],
                "security": [],
                "responses": {
                    "200": {
                        "description": "Service is ready",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ReadyResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/portfolio/state": {
            "get": {
                "summary": "Get portfolio state",
                "description": "Get current portfolio state with all positions and aggregate metrics.",
                "operationId": "getPortfolioState",
                "tags": ["Portfolio"],
                "responses": {
                    "200": {
                        "description": "Portfolio state with positions and trade stats",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "allOf": [
                                        {"$ref": "#/components/schemas/SuccessResponse"},
                                        {
                                            "properties": {
                                                "data": {
                                                    "properties": {
                                                        "attributes": {
                                                            "$ref": "#/components/schemas/PortfolioState",
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    ],
                                },
                            },
                        },
                    },
                    "401": {
                        "description": "Unauthorized",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                    "500": {
                        "description": "Internal server error",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/portfolio/positions": {
            "get": {
                "summary": "List open positions",
                "description": "List all open positions in the portfolio.",
                "operationId": "listPositions",
                "tags": ["Positions"],
                "responses": {
                    "200": {
                        "description": "Collection of open positions",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CollectionResponse"},
                            },
                        },
                    },
                    "401": {
                        "description": "Unauthorized",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/portfolio/positions/{instrument}": {
            "get": {
                "summary": "Get position for instrument",
                "description": "Get position details for a specific instrument.",
                "operationId": "getPosition",
                "tags": ["Positions"],
                "parameters": [
                    {
                        "name": "instrument",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "example": "BTC/USD",
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Position details",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SuccessResponse"},
                            },
                        },
                    },
                    "404": {
                        "description": "Position not found",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/portfolio/balance": {
            "get": {
                "summary": "Get account balance",
                "description": "Get account balance including total realized and unrealized P&L.",
                "operationId": "getBalance",
                "tags": ["Portfolio"],
                "responses": {
                    "200": {
                        "description": "Account balance",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "allOf": [
                                        {"$ref": "#/components/schemas/SuccessResponse"},
                                        {
                                            "properties": {
                                                "data": {
                                                    "properties": {
                                                        "attributes": {
                                                            "$ref": "#/components/schemas/Balance",
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    ],
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/portfolio/risk": {
            "get": {
                "summary": "Get risk metrics",
                "description": "Get risk metrics across all positions including exposure and concentration.",
                "operationId": "getRiskMetrics",
                "tags": ["Risk"],
                "responses": {
                    "200": {
                        "description": "Risk metrics",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "allOf": [
                                        {"$ref": "#/components/schemas/SuccessResponse"},
                                        {
                                            "properties": {
                                                "data": {
                                                    "properties": {
                                                        "attributes": {
                                                            "$ref": "#/components/schemas/RiskMetrics",
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    ],
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/portfolio/validate": {
            "post": {
                "summary": "Validate trade",
                "description": "Validate a proposed trade against risk limits.",
                "operationId": "validateTrade",
                "tags": ["Risk"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/TradeValidationRequest"},
                        },
                    },
                },
                "responses": {
                    "200": {
                        "description": "Validation result",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "allOf": [
                                        {"$ref": "#/components/schemas/SuccessResponse"},
                                        {
                                            "properties": {
                                                "data": {
                                                    "properties": {
                                                        "attributes": {
                                                            "$ref": "#/components/schemas/TradeValidationResult",
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    ],
                                },
                            },
                        },
                    },
                    "422": {
                        "description": "Validation error",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
        # ===================================================================
        # Strategy API — /api/v1/strategies
        # ===================================================================
        "/api/v1/strategies/health": {
            "get": {
                "summary": "Strategy API health check",
                "operationId": "strategyHealth",
                "tags": ["Health"],
                "security": [],
                "responses": {
                    "200": {
                        "description": "Service is healthy",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/strategies/ready": {
            "get": {
                "summary": "Strategy API readiness check",
                "operationId": "strategyReady",
                "tags": ["Health"],
                "security": [],
                "responses": {
                    "200": {
                        "description": "Service is ready",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ReadyResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/strategies/specs": {
            "get": {
                "summary": "List strategy specs",
                "description": "List strategy specifications with pagination and optional category filter.",
                "operationId": "listSpecs",
                "tags": ["Specs"],
                "parameters": [
                    {
                        "name": "category",
                        "in": "query",
                        "description": "Filter by category",
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "active",
                        "in": "query",
                        "description": "Filter by active status",
                        "schema": {"type": "boolean", "default": True},
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "description": "Maximum items to return",
                        "schema": {"type": "integer", "default": 50, "minimum": 1, "maximum": 1000},
                    },
                    {
                        "name": "offset",
                        "in": "query",
                        "description": "Number of items to skip",
                        "schema": {"type": "integer", "default": 0, "minimum": 0},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Paginated list of strategy specs",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CollectionResponse"},
                            },
                        },
                    },
                },
            },
            "post": {
                "summary": "Create strategy spec",
                "description": "Create a new strategy specification.",
                "operationId": "createSpec",
                "tags": ["Specs"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/StrategySpecCreate"},
                        },
                    },
                },
                "responses": {
                    "201": {
                        "description": "Spec created",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SuccessResponse"},
                            },
                        },
                    },
                    "409": {
                        "description": "Spec name already exists",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                    "500": {
                        "description": "Internal server error",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/strategies/specs/{spec_id}": {
            "get": {
                "summary": "Get strategy spec",
                "description": "Get a specific strategy specification by ID.",
                "operationId": "getSpec",
                "tags": ["Specs"],
                "parameters": [
                    {
                        "name": "spec_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "format": "uuid"},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Strategy spec details",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SuccessResponse"},
                            },
                        },
                    },
                    "404": {
                        "description": "Spec not found",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
            "put": {
                "summary": "Update strategy spec",
                "description": "Partially update a strategy specification.",
                "operationId": "updateSpec",
                "tags": ["Specs"],
                "parameters": [
                    {
                        "name": "spec_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "format": "uuid"},
                    },
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/StrategySpecUpdate"},
                        },
                    },
                },
                "responses": {
                    "200": {
                        "description": "Updated spec",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SuccessResponse"},
                            },
                        },
                    },
                    "404": {
                        "description": "Spec not found",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                    "422": {
                        "description": "No fields to update",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
            "delete": {
                "summary": "Delete strategy spec",
                "description": "Delete a strategy specification by ID.",
                "operationId": "deleteSpec",
                "tags": ["Specs"],
                "parameters": [
                    {
                        "name": "spec_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "format": "uuid"},
                    },
                ],
                "responses": {
                    "204": {
                        "description": "Spec deleted",
                    },
                    "404": {
                        "description": "Spec not found",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/strategies/specs/{spec_id}/implementations": {
            "get": {
                "summary": "List implementations for spec",
                "description": "List all implementations for a strategy specification.",
                "operationId": "listSpecImplementations",
                "tags": ["Implementations"],
                "parameters": [
                    {
                        "name": "spec_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "format": "uuid"},
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 50},
                    },
                    {
                        "name": "offset",
                        "in": "query",
                        "schema": {"type": "integer", "default": 0},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Paginated list of implementations",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CollectionResponse"},
                            },
                        },
                    },
                },
            },
            "post": {
                "summary": "Create implementation",
                "description": "Create a new implementation for a strategy specification.",
                "operationId": "createImplementation",
                "tags": ["Implementations"],
                "parameters": [
                    {
                        "name": "spec_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "format": "uuid"},
                    },
                ],
                "responses": {
                    "201": {
                        "description": "Implementation created",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SuccessResponse"},
                            },
                        },
                    },
                    "404": {
                        "description": "Spec not found",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/strategies/implementations": {
            "get": {
                "summary": "List implementations",
                "description": "List all strategy implementations with optional filtering by Sharpe ratio, instrument, and sorting.",
                "operationId": "listImplementations",
                "tags": ["Implementations"],
                "parameters": [
                    {
                        "name": "min_sharpe",
                        "in": "query",
                        "description": "Minimum Sharpe ratio",
                        "schema": {"type": "number", "format": "double"},
                    },
                    {
                        "name": "instrument",
                        "in": "query",
                        "description": "Filter by instrument",
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "order_by",
                        "in": "query",
                        "description": "Sort field",
                        "schema": {
                            "type": "string",
                            "enum": ["sharpe", "win_rate", "created_at"],
                        },
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 50},
                    },
                    {
                        "name": "offset",
                        "in": "query",
                        "schema": {"type": "integer", "default": 0},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Paginated list of implementations",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CollectionResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/strategies/implementations/{impl_id}": {
            "get": {
                "summary": "Get implementation",
                "description": "Get a specific strategy implementation by ID.",
                "operationId": "getImplementation",
                "tags": ["Implementations"],
                "parameters": [
                    {
                        "name": "impl_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "format": "uuid"},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Implementation details",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SuccessResponse"},
                            },
                        },
                    },
                    "404": {
                        "description": "Implementation not found",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
            "delete": {
                "summary": "Deactivate implementation",
                "description": "Deactivate a strategy implementation (sets status to INACTIVE).",
                "operationId": "deactivateImplementation",
                "tags": ["Implementations"],
                "parameters": [
                    {
                        "name": "impl_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "format": "uuid"},
                    },
                ],
                "responses": {
                    "204": {
                        "description": "Implementation deactivated",
                    },
                    "404": {
                        "description": "Implementation not found",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/strategies/implementations/{impl_id}/evaluate": {
            "post": {
                "summary": "Evaluate implementation",
                "description": "Submit backtesting evaluation for a strategy implementation.",
                "operationId": "evaluateImplementation",
                "tags": ["Implementations"],
                "parameters": [
                    {
                        "name": "impl_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "format": "uuid"},
                    },
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/EvaluateRequest"},
                        },
                    },
                },
                "responses": {
                    "200": {
                        "description": "Backtest submitted",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "allOf": [
                                        {"$ref": "#/components/schemas/SuccessResponse"},
                                        {
                                            "properties": {
                                                "data": {
                                                    "properties": {
                                                        "attributes": {
                                                            "$ref": "#/components/schemas/BacktestResult",
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    ],
                                },
                            },
                        },
                    },
                    "404": {
                        "description": "Implementation not found",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/strategies/implementations/{impl_id}/signal": {
            "get": {
                "summary": "Get cached signal",
                "description": "Get the latest cached signal for a strategy implementation and instrument.",
                "operationId": "getSignal",
                "tags": ["Implementations"],
                "parameters": [
                    {
                        "name": "impl_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "format": "uuid"},
                    },
                    {
                        "name": "instrument",
                        "in": "query",
                        "required": True,
                        "description": "Trading instrument",
                        "schema": {"type": "string"},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Signal data",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "allOf": [
                                        {"$ref": "#/components/schemas/SuccessResponse"},
                                        {
                                            "properties": {
                                                "data": {
                                                    "properties": {
                                                        "attributes": {
                                                            "$ref": "#/components/schemas/Signal",
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    ],
                                },
                            },
                        },
                    },
                    "404": {
                        "description": "Implementation or signal not found",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
        # ===================================================================
        # Market Data API — /api/v1/market
        # ===================================================================
        "/api/v1/market/health": {
            "get": {
                "summary": "Market Data API health check",
                "operationId": "marketHealth",
                "tags": ["Health"],
                "security": [],
                "responses": {
                    "200": {
                        "description": "Service is healthy",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/market/ready": {
            "get": {
                "summary": "Market Data API readiness check",
                "operationId": "marketReady",
                "tags": ["Health"],
                "security": [],
                "responses": {
                    "200": {
                        "description": "Service is ready",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ReadyResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/market/instruments": {
            "get": {
                "summary": "List instruments",
                "description": "List all available trading instruments.",
                "operationId": "listInstruments",
                "tags": ["Instruments"],
                "responses": {
                    "200": {
                        "description": "Collection of instruments",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CollectionResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/market/instruments/{symbol}/candles": {
            "get": {
                "summary": "Get OHLCV candles",
                "description": "Get OHLCV candle data for an instrument.",
                "operationId": "getCandles",
                "tags": ["Instruments"],
                "parameters": [
                    {
                        "name": "symbol",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "example": "BTC/USD",
                    },
                    {
                        "name": "interval",
                        "in": "query",
                        "required": True,
                        "description": "Candle interval",
                        "schema": {
                            "type": "string",
                            "enum": ["1m", "5m", "15m", "1h", "4h", "1d"],
                        },
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "description": "Max candles to return",
                        "schema": {"type": "integer", "default": 100, "minimum": 1, "maximum": 1000},
                    },
                    {
                        "name": "from",
                        "in": "query",
                        "description": "Start time (RFC3339 or relative e.g. -1h)",
                        "schema": {"type": "string"},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Candle data",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CollectionResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/market/instruments/{symbol}/price": {
            "get": {
                "summary": "Get current price",
                "description": "Get the latest price for an instrument.",
                "operationId": "getPrice",
                "tags": ["Instruments"],
                "parameters": [
                    {
                        "name": "symbol",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "example": "BTC/USD",
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Current price",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "allOf": [
                                        {"$ref": "#/components/schemas/SuccessResponse"},
                                        {
                                            "properties": {
                                                "data": {
                                                    "properties": {
                                                        "attributes": {
                                                            "$ref": "#/components/schemas/Price",
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    ],
                                },
                            },
                        },
                    },
                    "404": {
                        "description": "Price not found",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/market/instruments/{symbol}/orderbook": {
            "get": {
                "summary": "Get order book",
                "description": "Get order book for an instrument. Currently returns a placeholder; requires live exchange connection.",
                "operationId": "getOrderBook",
                "tags": ["Instruments"],
                "parameters": [
                    {
                        "name": "symbol",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "depth",
                        "in": "query",
                        "description": "Order book depth",
                        "schema": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Order book data",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "allOf": [
                                        {"$ref": "#/components/schemas/SuccessResponse"},
                                        {
                                            "properties": {
                                                "data": {
                                                    "properties": {
                                                        "attributes": {
                                                            "$ref": "#/components/schemas/OrderBook",
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    ],
                                },
                            },
                        },
                    },
                },
            },
        },
        # ===================================================================
        # Learning API — /api/v1/learning
        # ===================================================================
        "/api/v1/learning/health": {
            "get": {
                "summary": "Learning API health check",
                "operationId": "learningHealth",
                "tags": ["Health"],
                "security": [],
                "responses": {
                    "200": {
                        "description": "Service is healthy",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/learning/ready": {
            "get": {
                "summary": "Learning API readiness check",
                "operationId": "learningReady",
                "tags": ["Health"],
                "security": [],
                "responses": {
                    "200": {
                        "description": "Service is ready",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ReadyResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/learning/decisions": {
            "get": {
                "summary": "List decisions",
                "description": "List agent decisions with optional filtering by instrument and date range.",
                "operationId": "listDecisions",
                "tags": ["Decisions"],
                "parameters": [
                    {
                        "name": "instrument",
                        "in": "query",
                        "description": "Filter by instrument",
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "from",
                        "in": "query",
                        "description": "Start datetime (ISO 8601)",
                        "schema": {"type": "string", "format": "date-time"},
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 50},
                    },
                    {
                        "name": "offset",
                        "in": "query",
                        "schema": {"type": "integer", "default": 0},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Paginated list of decisions",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CollectionResponse"},
                            },
                        },
                    },
                },
            },
            "post": {
                "summary": "Create decision",
                "description": "Record a new agent decision.",
                "operationId": "createDecision",
                "tags": ["Decisions"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/DecisionCreate"},
                        },
                    },
                },
                "responses": {
                    "201": {
                        "description": "Decision created",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SuccessResponse"},
                            },
                        },
                    },
                    "500": {
                        "description": "Internal server error",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/learning/decisions/{decision_id}": {
            "get": {
                "summary": "Get decision",
                "description": "Get a specific agent decision by ID.",
                "operationId": "getDecision",
                "tags": ["Decisions"],
                "parameters": [
                    {
                        "name": "decision_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "format": "uuid"},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Decision details",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SuccessResponse"},
                            },
                        },
                    },
                    "404": {
                        "description": "Decision not found",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/learning/decisions/{decision_id}/outcome": {
            "put": {
                "summary": "Record decision outcome",
                "description": "Record the outcome of an agent decision.",
                "operationId": "recordOutcome",
                "tags": ["Decisions"],
                "parameters": [
                    {
                        "name": "decision_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "format": "uuid"},
                    },
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/OutcomeUpdate"},
                        },
                    },
                },
                "responses": {
                    "200": {
                        "description": "Outcome recorded",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SuccessResponse"},
                            },
                        },
                    },
                    "404": {
                        "description": "Decision not found",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/learning/patterns": {
            "get": {
                "summary": "Detect performance patterns",
                "description": "Detect performance patterns from recent agent decisions (last 30 days).",
                "operationId": "getPatterns",
                "tags": ["Analytics"],
                "responses": {
                    "200": {
                        "description": "Performance patterns",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CollectionResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/learning/performance": {
            "get": {
                "summary": "Get performance metrics",
                "description": "Get aggregate performance metrics for agent decisions.",
                "operationId": "getPerformance",
                "tags": ["Analytics"],
                "parameters": [
                    {
                        "name": "instrument",
                        "in": "query",
                        "description": "Filter by instrument",
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "period",
                        "in": "query",
                        "description": "Time period",
                        "schema": {
                            "type": "string",
                            "enum": ["7d", "30d", "90d", "all"],
                            "default": "30d",
                        },
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Performance metrics",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "allOf": [
                                        {"$ref": "#/components/schemas/SuccessResponse"},
                                        {
                                            "properties": {
                                                "data": {
                                                    "properties": {
                                                        "attributes": {
                                                            "$ref": "#/components/schemas/PerformanceMetrics",
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    ],
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/learning/similar": {
            "post": {
                "summary": "Find similar situations",
                "description": "Find similar historical situations based on market context.",
                "operationId": "findSimilar",
                "tags": ["Analytics"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/MarketContext"},
                        },
                    },
                },
                "responses": {
                    "200": {
                        "description": "Similar historical situations",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CollectionResponse"},
                            },
                        },
                    },
                },
            },
        },
        # ===================================================================
        # Agent Gateway
        # ===================================================================
        "/api/v1/gateway/health": {
            "get": {
                "summary": "Agent Gateway health check",
                "description": "Returns connectivity status for the database and Redis.",
                "operationId": "gatewayHealth",
                "tags": ["Health"],
                "security": [],
                "responses": {
                    "200": {
                        "description": "Service is healthy",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string"},
                                        "service": {"type": "string"},
                                        "database": {"type": "string"},
                                        "redis": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                    "503": {
                        "description": "Service degraded",
                    },
                },
            },
        },
        "/api/v1/gateway/events/stream": {
            "get": {
                "summary": "Stream agent events (SSE)",
                "description": "Opens a persistent Server-Sent Events connection that pushes real-time agent events from Redis pub/sub.",
                "operationId": "streamEvents",
                "tags": ["Events"],
                "parameters": [
                    {
                        "name": "agent_name",
                        "in": "query",
                        "description": "Filter by agent name",
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "event_type",
                        "in": "query",
                        "description": "Filter by event type",
                        "schema": {
                            "type": "string",
                            "enum": ["signal", "reasoning", "tool_call", "decision"],
                        },
                    },
                ],
                "responses": {
                    "200": {
                        "description": "SSE event stream",
                        "content": {
                            "text/event-stream": {
                                "schema": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/gateway/events/recent": {
            "get": {
                "summary": "Get recent events",
                "description": "Get recent agent events from the database.",
                "operationId": "getRecentEvents",
                "tags": ["Events"],
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "description": "Number of events to return",
                        "schema": {"type": "integer", "default": 50, "minimum": 1, "maximum": 500},
                    },
                    {
                        "name": "agent_name",
                        "in": "query",
                        "description": "Filter by agent name",
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "event_type",
                        "in": "query",
                        "description": "Filter by event type",
                        "schema": {
                            "type": "string",
                            "enum": ["signal", "reasoning", "tool_call", "decision"],
                        },
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Recent events",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "events": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/AgentEvent"},
                                        },
                                        "count": {"type": "integer"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/gateway/dashboard/summary": {
            "get": {
                "summary": "Dashboard summary",
                "description": "High-level dashboard summary with active agents, 24h stats, tier distribution, and recent signals.",
                "operationId": "getDashboardSummary",
                "tags": ["Dashboard"],
                "responses": {
                    "200": {
                        "description": "Dashboard summary",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/DashboardSummary"},
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/gateway/dashboard/agents": {
            "get": {
                "summary": "Agent activity details",
                "description": "Get detailed agent activity and performance metrics.",
                "operationId": "getAgentDetails",
                "tags": ["Dashboard"],
                "parameters": [
                    {
                        "name": "agent_name",
                        "in": "query",
                        "description": "Specific agent to query",
                        "schema": {"type": "string"},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Agent details",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "agents": {
                                            "type": "array",
                                            "items": {"type": "object"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/v1/gateway/dashboard/signals": {
            "get": {
                "summary": "Signal activity",
                "description": "Get signal activity with scoring details for the dashboard.",
                "operationId": "getSignalActivity",
                "tags": ["Dashboard"],
                "parameters": [
                    {
                        "name": "hours",
                        "in": "query",
                        "description": "Lookback period in hours",
                        "schema": {"type": "integer", "default": 24, "minimum": 1, "maximum": 168},
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "description": "Max signals to return",
                        "schema": {"type": "integer", "default": 100, "minimum": 1, "maximum": 500},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Signal activity",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "signals": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/AgentEvent"},
                                        },
                                        "count": {"type": "integer"},
                                        "hours": {"type": "integer"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        # ===================================================================
        # Strategy Monitor API — /api
        # ===================================================================
        "/api/strategies": {
            "get": {
                "summary": "List monitored strategies",
                "description": "Retrieve all strategies with optional filtering by symbol, strategy type, minimum score, and result limit.",
                "operationId": "getMonitoredStrategies",
                "tags": ["Strategies"],
                "parameters": [
                    {
                        "name": "symbol",
                        "in": "query",
                        "description": "Filter by trading symbol (e.g. BTC/USD)",
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "strategy_type",
                        "in": "query",
                        "description": "Filter by strategy type",
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "min_score",
                        "in": "query",
                        "description": "Minimum score threshold",
                        "schema": {"type": "number", "format": "double"},
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "description": "Maximum results",
                        "schema": {"type": "integer", "default": 100},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "List of strategies",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "strategies": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/MonitoredStrategy"},
                                        },
                                        "count": {"type": "integer"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/strategies/{strategy_id}": {
            "get": {
                "summary": "Get strategy by ID",
                "description": "Get a specific monitored strategy by its ID.",
                "operationId": "getMonitoredStrategy",
                "tags": ["Strategies"],
                "parameters": [
                    {
                        "name": "strategy_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Strategy details",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/MonitoredStrategy"},
                            },
                        },
                    },
                    "404": {
                        "description": "Strategy not found",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/api/metrics": {
            "get": {
                "summary": "Get strategy metrics",
                "description": "Get aggregated strategy metrics including counts by type and symbol.",
                "operationId": "getStrategyMetrics",
                "tags": ["Strategies"],
                "responses": {
                    "200": {
                        "description": "Aggregated metrics",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/StrategyMetrics"},
                            },
                        },
                    },
                },
            },
        },
        "/api/symbols": {
            "get": {
                "summary": "List symbols",
                "description": "List unique trading symbols used by strategies.",
                "operationId": "getSymbols",
                "tags": ["Strategies"],
                "responses": {
                    "200": {
                        "description": "Symbol list",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "symbols": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/strategy-types": {
            "get": {
                "summary": "List strategy types",
                "description": "List all available strategy types.",
                "operationId": "getStrategyTypes",
                "tags": ["Strategies"],
                "responses": {
                    "200": {
                        "description": "Strategy type list",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "strategy_types": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/health": {
            "get": {
                "summary": "Strategy Monitor health check",
                "operationId": "strategyMonitorHealth",
                "tags": ["Health"],
                "security": [],
                "responses": {
                    "200": {
                        "description": "Service is healthy",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthResponse"},
                            },
                        },
                    },
                },
            },
        },
        # ===================================================================
        # Paper Trading — /paper
        # ===================================================================
        "/paper/health": {
            "get": {
                "summary": "Paper Trading health check",
                "operationId": "paperTradingHealth",
                "tags": ["Health"],
                "security": [],
                "responses": {
                    "200": {
                        "description": "Service is healthy",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/paper/execute": {
            "post": {
                "summary": "Execute paper trade",
                "description": "Simulate a trade from a signal. Fetches signal details, gets current market price, and records the paper trade.",
                "operationId": "executePaperTrade",
                "tags": ["Paper Trading"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/PaperTradeRequest"},
                        },
                    },
                },
                "responses": {
                    "201": {
                        "description": "Trade executed",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PaperTrade"},
                            },
                        },
                    },
                    "400": {
                        "description": "Invalid request (missing fields or invalid signal action)",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                    "404": {
                        "description": "Signal not found",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                    "502": {
                        "description": "Could not get market price",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/paper/portfolio": {
            "get": {
                "summary": "Get paper portfolio",
                "description": "Get current paper portfolio positions with live unrealized P&L.",
                "operationId": "getPaperPortfolio",
                "tags": ["Paper Trading"],
                "responses": {
                    "200": {
                        "description": "Portfolio positions",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PaperPortfolio"},
                            },
                        },
                    },
                    "500": {
                        "description": "Internal server error",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/paper/trades": {
            "get": {
                "summary": "Get paper trades",
                "description": "Get paper trades with optional filters by symbol, status, and limit.",
                "operationId": "getPaperTrades",
                "tags": ["Paper Trading"],
                "parameters": [
                    {
                        "name": "symbol",
                        "in": "query",
                        "description": "Filter by symbol",
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "status",
                        "in": "query",
                        "description": "Filter by status",
                        "schema": {"type": "string", "enum": ["OPEN", "CLOSED"]},
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "description": "Max results",
                        "schema": {"type": "integer", "default": 50},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Paper trades",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "trades": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/PaperTrade"},
                                        },
                                        "count": {"type": "integer"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "/paper/pnl-summary": {
            "get": {
                "summary": "Get P&L summary",
                "description": "Get aggregated P&L summary with optional symbol filter.",
                "operationId": "getPnlSummary",
                "tags": ["Paper Trading"],
                "parameters": [
                    {
                        "name": "symbol",
                        "in": "query",
                        "description": "Filter by symbol",
                        "schema": {"type": "string"},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "P&L summary",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PnlSummary"},
                            },
                        },
                    },
                },
            },
        },
        # ===================================================================
        # Portfolio State — /portfolio
        # ===================================================================
        "/portfolio/health": {
            "get": {
                "summary": "Portfolio State health check",
                "operationId": "portfolioStateHealth",
                "tags": ["Health"],
                "security": [],
                "responses": {
                    "200": {
                        "description": "Service is healthy",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/portfolio/state": {
            "get": {
                "summary": "Get full portfolio state",
                "description": "Get full portfolio state including positions, balance, risk metrics, and recent trades.",
                "operationId": "getFullPortfolioState",
                "tags": ["Portfolio State"],
                "responses": {
                    "200": {
                        "description": "Full portfolio state",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/FullPortfolioState"},
                            },
                        },
                    },
                    "500": {
                        "description": "Internal server error",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
        "/portfolio/context": {
            "get": {
                "summary": "Get portfolio context",
                "description": "Get formatted portfolio context string for decision agent prompts.",
                "operationId": "getPortfolioContext",
                "tags": ["Portfolio State"],
                "responses": {
                    "200": {
                        "description": "Portfolio context string",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "context": {"type": "string"},
                                        "as_of": {"type": "string", "format": "date-time"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "/portfolio/positions": {
            "get": {
                "summary": "Get positions with live prices",
                "description": "Get current open positions with live market prices.",
                "operationId": "getPortfolioStatePositions",
                "tags": ["Portfolio State"],
                "responses": {
                    "200": {
                        "description": "Positions with live data",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "positions": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/DetailedPosition"},
                                        },
                                        "count": {"type": "integer"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "/portfolio/risk": {
            "get": {
                "summary": "Get portfolio risk metrics",
                "description": "Get current risk metrics including portfolio heat, max position, and daily drawdown.",
                "operationId": "getPortfolioRisk",
                "tags": ["Portfolio State"],
                "responses": {
                    "200": {
                        "description": "Risk metrics",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/FullRiskMetrics"},
                            },
                        },
                    },
                },
            },
        },
        "/portfolio/validate": {
            "post": {
                "summary": "Validate trade decision",
                "description": "Validate a proposed trade decision against portfolio constraints (position size, portfolio heat).",
                "operationId": "validateDecision",
                "tags": ["Portfolio State"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/DecisionValidateRequest"},
                        },
                    },
                },
                "responses": {
                    "200": {
                        "description": "Validation result",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "valid": {"type": "boolean"},
                                        "errors": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "warnings": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                    "400": {
                        "description": "Missing required fields",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            },
                        },
                    },
                },
            },
        },
    },
}


def get_spec() -> dict:
    """Return the complete OpenAPI spec as a dict."""
    return OPENAPI_SPEC
