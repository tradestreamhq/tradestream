"""Backtesting API endpoints and schemas for the OpenAPI spec."""

BACKTESTING_TAGS = [
    {
        "name": "Backtesting",
        "description": "Run backtests, walk-forward analysis, and optimization across strategies",
    },
]

BACKTESTING_SCHEMAS = {
    "BacktestRequest": {
        "type": "object",
        "properties": {
            "strategy_id": {"type": "string", "format": "uuid"},
            "instrument": {"type": "string", "example": "BTC/USD"},
            "start_date": {
                "type": "string",
                "format": "date",
                "example": "2025-01-01",
            },
            "end_date": {
                "type": "string",
                "format": "date",
                "example": "2026-01-01",
            },
            "timeframe": {
                "type": "string",
                "enum": ["1m", "5m", "15m", "1h", "4h", "1d"],
                "example": "4h",
            },
            "initial_capital": {
                "type": "number",
                "format": "double",
                "example": 10000.0,
            },
            "commission_pct": {
                "type": "number",
                "format": "double",
                "description": "Commission per trade as percentage",
                "example": 0.1,
            },
            "slippage_pct": {
                "type": "number",
                "format": "double",
                "description": "Estimated slippage per trade as percentage",
                "example": 0.05,
            },
            "parameters": {
                "type": "object",
                "description": "Strategy-specific parameter overrides",
                "example": {"rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70},
            },
        },
        "required": ["strategy_id", "instrument", "start_date", "end_date"],
    },
    "BacktestResponse": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "status": {
                "type": "string",
                "enum": ["queued", "running", "completed", "failed"],
                "example": "completed",
            },
            "strategy_id": {"type": "string", "format": "uuid"},
            "instrument": {"type": "string"},
            "period": {
                "type": "object",
                "properties": {
                    "start": {"type": "string", "format": "date"},
                    "end": {"type": "string", "format": "date"},
                },
            },
            "metrics": {"$ref": "#/components/schemas/BacktestMetrics"},
            "trades": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/BacktestTrade"},
            },
            "equity_curve": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "timestamp": {"type": "string", "format": "date-time"},
                        "equity": {"type": "number", "format": "double"},
                    },
                },
            },
            "created_at": {"type": "string", "format": "date-time"},
            "completed_at": {"type": "string", "format": "date-time"},
            "duration_ms": {"type": "integer", "description": "Execution time in milliseconds"},
        },
    },
    "BacktestMetrics": {
        "type": "object",
        "properties": {
            "total_return_pct": {"type": "number", "format": "double", "example": 42.3},
            "annualized_return_pct": {"type": "number", "format": "double", "example": 38.7},
            "sharpe_ratio": {"type": "number", "format": "double", "example": 1.85},
            "sortino_ratio": {"type": "number", "format": "double", "example": 2.31},
            "max_drawdown_pct": {"type": "number", "format": "double", "example": -12.5},
            "calmar_ratio": {"type": "number", "format": "double", "example": 3.1},
            "win_rate": {"type": "number", "format": "double", "example": 0.62},
            "profit_factor": {"type": "number", "format": "double", "example": 1.73},
            "total_trades": {"type": "integer", "example": 312},
            "avg_trade_return_pct": {"type": "number", "format": "double", "example": 0.14},
            "avg_win_pct": {"type": "number", "format": "double", "example": 1.8},
            "avg_loss_pct": {"type": "number", "format": "double", "example": -1.04},
            "avg_trade_duration_hours": {"type": "number", "format": "double"},
            "max_consecutive_wins": {"type": "integer"},
            "max_consecutive_losses": {"type": "integer"},
            "expectancy": {"type": "number", "format": "double"},
        },
    },
    "BacktestTrade": {
        "type": "object",
        "properties": {
            "entry_time": {"type": "string", "format": "date-time"},
            "exit_time": {"type": "string", "format": "date-time"},
            "direction": {"type": "string", "enum": ["BUY", "SELL"]},
            "entry_price": {"type": "number", "format": "double"},
            "exit_price": {"type": "number", "format": "double"},
            "quantity": {"type": "number", "format": "double"},
            "pnl": {"type": "number", "format": "double"},
            "pnl_pct": {"type": "number", "format": "double"},
            "exit_reason": {
                "type": "string",
                "enum": ["signal", "stop_loss", "take_profit", "timeout"],
            },
        },
    },
    "WalkForwardRequest": {
        "type": "object",
        "properties": {
            "strategy_id": {"type": "string", "format": "uuid"},
            "instrument": {"type": "string"},
            "start_date": {"type": "string", "format": "date"},
            "end_date": {"type": "string", "format": "date"},
            "in_sample_pct": {
                "type": "number",
                "minimum": 0.5,
                "maximum": 0.9,
                "description": "Percentage of each window used for in-sample optimization",
                "example": 0.7,
            },
            "num_windows": {
                "type": "integer",
                "minimum": 2,
                "maximum": 20,
                "description": "Number of walk-forward windows",
                "example": 5,
            },
            "parameters": {"type": "object"},
        },
        "required": ["strategy_id", "instrument", "start_date", "end_date"],
    },
    "WalkForwardResponse": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "windows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "window_num": {"type": "integer"},
                        "in_sample_start": {"type": "string", "format": "date"},
                        "in_sample_end": {"type": "string", "format": "date"},
                        "out_of_sample_start": {"type": "string", "format": "date"},
                        "out_of_sample_end": {"type": "string", "format": "date"},
                        "in_sample_sharpe": {"type": "number", "format": "double"},
                        "out_of_sample_sharpe": {"type": "number", "format": "double"},
                        "degradation_pct": {"type": "number", "format": "double"},
                    },
                },
            },
            "aggregate_metrics": {"$ref": "#/components/schemas/BacktestMetrics"},
            "robustness_score": {
                "type": "number",
                "format": "double",
                "description": "0-1 score indicating strategy robustness across windows",
            },
        },
    },
    "OptimizationRequest": {
        "type": "object",
        "properties": {
            "strategy_id": {"type": "string", "format": "uuid"},
            "instrument": {"type": "string"},
            "start_date": {"type": "string", "format": "date"},
            "end_date": {"type": "string", "format": "date"},
            "parameter_ranges": {
                "type": "object",
                "description": "Parameter name to [min, max, step] mapping",
                "example": {
                    "rsi_period": [7, 21, 1],
                    "rsi_oversold": [20, 40, 5],
                    "rsi_overbought": [60, 80, 5],
                },
            },
            "optimization_target": {
                "type": "string",
                "enum": ["sharpe", "return", "calmar", "sortino"],
                "default": "sharpe",
            },
            "max_combinations": {
                "type": "integer",
                "description": "Cap on parameter combinations to evaluate",
                "default": 1000,
            },
        },
        "required": ["strategy_id", "instrument", "start_date", "end_date", "parameter_ranges"],
    },
    "OptimizationResponse": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "best_parameters": {"type": "object"},
            "best_metrics": {"$ref": "#/components/schemas/BacktestMetrics"},
            "total_combinations_tested": {"type": "integer"},
            "top_results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "parameters": {"type": "object"},
                        "metrics": {"$ref": "#/components/schemas/BacktestMetrics"},
                    },
                },
                "description": "Top 10 parameter combinations",
            },
            "duration_ms": {"type": "integer"},
        },
    },
}

BACKTESTING_PATHS = {
    "/api/v1/backtests": {
        "get": {
            "summary": "List backtests",
            "description": "List previous backtest runs with optional filtering.",
            "operationId": "listBacktests",
            "tags": ["Backtesting"],
            "parameters": [
                {"name": "strategy_id", "in": "query", "schema": {"type": "string", "format": "uuid"}},
                {"name": "instrument", "in": "query", "schema": {"type": "string"}},
                {
                    "name": "status",
                    "in": "query",
                    "schema": {"type": "string", "enum": ["queued", "running", "completed", "failed"]},
                },
                {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 20}},
                {"name": "offset", "in": "query", "schema": {"type": "integer", "default": 0}},
            ],
            "responses": {
                "200": {
                    "description": "Paginated backtest list",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/CollectionResponse"},
                        },
                    },
                },
            },
        },
        "post": {
            "summary": "Run a backtest",
            "description": (
                "Submit a backtest job. The backtest runs asynchronously — poll the "
                "returned ID for results, or use the SSE endpoint to stream progress."
            ),
            "operationId": "runBacktest",
            "tags": ["Backtesting"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/BacktestRequest"},
                        "example": {
                            "strategy_id": "strat_abc123",
                            "instrument": "BTC/USD",
                            "start_date": "2025-01-01",
                            "end_date": "2026-01-01",
                            "timeframe": "4h",
                            "initial_capital": 10000,
                            "parameters": {"rsi_period": 14, "rsi_oversold": 30},
                        },
                    },
                },
            },
            "responses": {
                "202": {
                    "description": "Backtest queued",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string", "format": "uuid"},
                                    "status": {"type": "string", "example": "queued"},
                                },
                            },
                        },
                    },
                },
                "400": {
                    "description": "Invalid parameters",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
                "429": {
                    "description": "Backtest quota exceeded",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/backtests/{backtest_id}": {
        "get": {
            "summary": "Get backtest results",
            "description": "Retrieve full results for a completed backtest including metrics, trades, and equity curve.",
            "operationId": "getBacktest",
            "tags": ["Backtesting"],
            "parameters": [
                {
                    "name": "backtest_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
                {
                    "name": "include_trades",
                    "in": "query",
                    "schema": {"type": "boolean", "default": True},
                    "description": "Include individual trade list (can be large)",
                },
                {
                    "name": "include_equity_curve",
                    "in": "query",
                    "schema": {"type": "boolean", "default": False},
                    "description": "Include equity curve data points",
                },
            ],
            "responses": {
                "200": {
                    "description": "Backtest results",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/BacktestResponse"},
                        },
                    },
                },
                "404": {
                    "description": "Backtest not found",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/backtests/{backtest_id}/compare": {
        "get": {
            "summary": "Compare backtest to benchmark",
            "description": "Compare backtest performance against buy-and-hold or another backtest.",
            "operationId": "compareBacktest",
            "tags": ["Backtesting"],
            "parameters": [
                {
                    "name": "backtest_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
                {
                    "name": "benchmark",
                    "in": "query",
                    "schema": {
                        "type": "string",
                        "default": "buy_and_hold",
                    },
                    "description": "Benchmark to compare against (buy_and_hold or another backtest_id)",
                },
            ],
            "responses": {
                "200": {
                    "description": "Comparison results",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "strategy": {"$ref": "#/components/schemas/BacktestMetrics"},
                                    "benchmark": {"$ref": "#/components/schemas/BacktestMetrics"},
                                    "alpha": {"type": "number", "format": "double"},
                                    "beta": {"type": "number", "format": "double"},
                                    "information_ratio": {"type": "number", "format": "double"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "/api/v1/backtests/walk-forward": {
        "post": {
            "summary": "Run walk-forward analysis",
            "description": (
                "Run walk-forward validation to assess strategy robustness. "
                "Splits data into in-sample/out-of-sample windows."
            ),
            "operationId": "runWalkForward",
            "tags": ["Backtesting"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/WalkForwardRequest"},
                    },
                },
            },
            "responses": {
                "202": {
                    "description": "Walk-forward analysis queued",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string", "format": "uuid"},
                                    "status": {"type": "string", "example": "queued"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "/api/v1/backtests/walk-forward/{wf_id}": {
        "get": {
            "summary": "Get walk-forward results",
            "description": "Retrieve walk-forward analysis results.",
            "operationId": "getWalkForwardResults",
            "tags": ["Backtesting"],
            "parameters": [
                {
                    "name": "wf_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
            ],
            "responses": {
                "200": {
                    "description": "Walk-forward results",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/WalkForwardResponse"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/backtests/optimize": {
        "post": {
            "summary": "Run parameter optimization",
            "description": "Grid search or random search over strategy parameters to find optimal configuration.",
            "operationId": "runOptimization",
            "tags": ["Backtesting"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/OptimizationRequest"},
                    },
                },
            },
            "responses": {
                "202": {
                    "description": "Optimization job queued",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string", "format": "uuid"},
                                    "status": {"type": "string", "example": "queued"},
                                    "estimated_combinations": {"type": "integer"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "/api/v1/backtests/optimize/{opt_id}": {
        "get": {
            "summary": "Get optimization results",
            "description": "Retrieve parameter optimization results with top-performing configurations.",
            "operationId": "getOptimizationResults",
            "tags": ["Backtesting"],
            "parameters": [
                {
                    "name": "opt_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
            ],
            "responses": {
                "200": {
                    "description": "Optimization results",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/OptimizationResponse"},
                        },
                    },
                },
            },
        },
    },
}
