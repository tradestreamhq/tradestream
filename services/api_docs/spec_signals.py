"""Signal Service API endpoints and schemas for the OpenAPI spec."""

SIGNAL_TAGS = [
    {
        "name": "Signals",
        "description": "Trading signal generation, subscription, and delivery",
    },
    {
        "name": "Signal Subscriptions",
        "description": "Subscribe to and manage signal feeds",
    },
]

SIGNAL_SCHEMAS = {
    "Signal": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid", "example": "sig_abc123"},
            "strategy_id": {"type": "string", "format": "uuid"},
            "instrument": {"type": "string", "example": "BTC/USD"},
            "direction": {
                "type": "string",
                "enum": ["BUY", "SELL", "HOLD"],
                "example": "BUY",
            },
            "strength": {
                "type": "number",
                "format": "double",
                "minimum": 0,
                "maximum": 1,
                "description": "Signal confidence score (0-1)",
                "example": 0.85,
            },
            "entry_price": {"type": "number", "format": "double", "example": 67500.00},
            "stop_loss": {"type": "number", "format": "double", "example": 66000.00},
            "take_profit": {"type": "number", "format": "double", "example": 70000.00},
            "timeframe": {
                "type": "string",
                "enum": ["1m", "5m", "15m", "1h", "4h", "1d"],
                "example": "4h",
            },
            "metadata": {
                "type": "object",
                "description": "Strategy-specific metadata (indicators, reasoning)",
                "example": {
                    "rsi": 32.5,
                    "macd_crossover": True,
                    "reasoning": "RSI oversold with MACD bullish crossover",
                },
            },
            "created_at": {"type": "string", "format": "date-time"},
            "expires_at": {
                "type": "string",
                "format": "date-time",
                "description": "Signal expiration timestamp",
            },
            "status": {
                "type": "string",
                "enum": ["active", "expired", "filled", "cancelled"],
                "example": "active",
            },
        },
        "required": [
            "id",
            "strategy_id",
            "instrument",
            "direction",
            "strength",
            "created_at",
        ],
    },
    "SignalSubscription": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "user_id": {"type": "string", "format": "uuid"},
            "strategy_id": {"type": "string", "format": "uuid"},
            "delivery_channels": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["webhook", "email", "telegram", "discord"],
                },
                "example": ["webhook", "telegram"],
            },
            "filters": {
                "$ref": "#/components/schemas/SignalFilter",
            },
            "active": {"type": "boolean", "example": True},
            "created_at": {"type": "string", "format": "date-time"},
        },
        "required": ["id", "user_id", "strategy_id", "delivery_channels"],
    },
    "SignalFilter": {
        "type": "object",
        "description": "Filters to apply before delivering signals",
        "properties": {
            "min_strength": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Minimum signal strength to deliver",
                "example": 0.7,
            },
            "instruments": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Instrument whitelist (empty = all)",
                "example": ["BTC/USD", "ETH/USD"],
            },
            "directions": {
                "type": "array",
                "items": {"type": "string", "enum": ["BUY", "SELL"]},
                "description": "Direction filter",
            },
            "timeframes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Timeframe filter",
                "example": ["1h", "4h", "1d"],
            },
        },
    },
    "CreateSubscriptionRequest": {
        "type": "object",
        "properties": {
            "strategy_id": {"type": "string", "format": "uuid"},
            "delivery_channels": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["webhook", "email", "telegram", "discord"],
                },
            },
            "webhook_url": {
                "type": "string",
                "format": "uri",
                "description": "Required if 'webhook' is in delivery_channels",
                "example": "https://your-app.com/webhook/signals",
            },
            "filters": {"$ref": "#/components/schemas/SignalFilter"},
        },
        "required": ["strategy_id", "delivery_channels"],
    },
    "SignalDeliveryLog": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "signal_id": {"type": "string", "format": "uuid"},
            "subscription_id": {"type": "string", "format": "uuid"},
            "channel": {
                "type": "string",
                "enum": ["webhook", "email", "telegram", "discord"],
            },
            "status": {
                "type": "string",
                "enum": ["delivered", "failed", "pending", "retrying"],
            },
            "response_code": {"type": "integer", "example": 200},
            "delivered_at": {"type": "string", "format": "date-time"},
            "error_message": {"type": "string"},
        },
    },
}

SIGNAL_PATHS = {
    "/api/v1/signals": {
        "get": {
            "summary": "List signals",
            "description": (
                "Retrieve trading signals with optional filtering by instrument, "
                "direction, strategy, and time range. Results are paginated."
            ),
            "operationId": "listSignals",
            "tags": ["Signals"],
            "parameters": [
                {
                    "name": "instrument",
                    "in": "query",
                    "schema": {"type": "string"},
                    "description": "Filter by instrument symbol",
                    "example": "BTC/USD",
                },
                {
                    "name": "direction",
                    "in": "query",
                    "schema": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
                },
                {
                    "name": "strategy_id",
                    "in": "query",
                    "schema": {"type": "string", "format": "uuid"},
                },
                {
                    "name": "status",
                    "in": "query",
                    "schema": {
                        "type": "string",
                        "enum": ["active", "expired", "filled", "cancelled"],
                    },
                },
                {
                    "name": "min_strength",
                    "in": "query",
                    "schema": {"type": "number", "minimum": 0, "maximum": 1},
                },
                {
                    "name": "since",
                    "in": "query",
                    "schema": {"type": "string", "format": "date-time"},
                    "description": "Return signals after this timestamp",
                },
                {
                    "name": "limit",
                    "in": "query",
                    "schema": {
                        "type": "integer",
                        "default": 50,
                        "minimum": 1,
                        "maximum": 200,
                    },
                },
                {
                    "name": "offset",
                    "in": "query",
                    "schema": {"type": "integer", "default": 0, "minimum": 0},
                },
            ],
            "responses": {
                "200": {
                    "description": "Paginated list of signals",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/CollectionResponse"
                            },
                            "example": {
                                "data": [
                                    {
                                        "type": "signal",
                                        "id": "sig_abc123",
                                        "attributes": {
                                            "instrument": "BTC/USD",
                                            "direction": "BUY",
                                            "strength": 0.85,
                                            "entry_price": 67500.00,
                                            "stop_loss": 66000.00,
                                            "take_profit": 70000.00,
                                            "timeframe": "4h",
                                            "status": "active",
                                            "created_at": "2026-03-19T10:00:00Z",
                                        },
                                    }
                                ],
                                "meta": {"total": 142, "limit": 50, "offset": 0},
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
            },
        },
    },
    "/api/v1/signals/{signal_id}": {
        "get": {
            "summary": "Get signal by ID",
            "description": "Retrieve a specific trading signal with full details including metadata.",
            "operationId": "getSignal",
            "tags": ["Signals"],
            "parameters": [
                {
                    "name": "signal_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
            ],
            "responses": {
                "200": {
                    "description": "Signal details",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Signal"},
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
            },
        },
    },
    "/api/v1/signals/latest": {
        "get": {
            "summary": "Get latest signal per instrument",
            "description": "Returns the most recent active signal for each instrument, useful for dashboard views.",
            "operationId": "getLatestSignals",
            "tags": ["Signals"],
            "parameters": [
                {
                    "name": "instruments",
                    "in": "query",
                    "schema": {"type": "string"},
                    "description": "Comma-separated instrument list",
                    "example": "BTC/USD,ETH/USD",
                },
            ],
            "responses": {
                "200": {
                    "description": "Latest signals per instrument",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "additionalProperties": {
                                    "$ref": "#/components/schemas/Signal",
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "/api/v1/signals/subscriptions": {
        "get": {
            "summary": "List signal subscriptions",
            "description": "List all signal subscriptions for the authenticated user.",
            "operationId": "listSubscriptions",
            "tags": ["Signal Subscriptions"],
            "parameters": [
                {
                    "name": "active",
                    "in": "query",
                    "schema": {"type": "boolean"},
                    "description": "Filter by active status",
                },
            ],
            "responses": {
                "200": {
                    "description": "List of subscriptions",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/CollectionResponse"
                            },
                        },
                    },
                },
            },
        },
        "post": {
            "summary": "Create signal subscription",
            "description": (
                "Subscribe to signals from a strategy. Configure delivery channels "
                "(webhook, email, Telegram, Discord) and optional filters."
            ),
            "operationId": "createSubscription",
            "tags": ["Signal Subscriptions"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/CreateSubscriptionRequest"
                        },
                        "example": {
                            "strategy_id": "strat_xyz789",
                            "delivery_channels": ["webhook", "telegram"],
                            "webhook_url": "https://your-app.com/webhook/signals",
                            "filters": {
                                "min_strength": 0.7,
                                "instruments": ["BTC/USD", "ETH/USD"],
                                "timeframes": ["4h", "1d"],
                            },
                        },
                    },
                },
            },
            "responses": {
                "201": {
                    "description": "Subscription created",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/SignalSubscription"
                            },
                        },
                    },
                },
                "400": {
                    "description": "Invalid subscription parameters",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/signals/subscriptions/{subscription_id}": {
        "get": {
            "summary": "Get subscription details",
            "description": "Retrieve details of a specific signal subscription.",
            "operationId": "getSubscription",
            "tags": ["Signal Subscriptions"],
            "parameters": [
                {
                    "name": "subscription_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
            ],
            "responses": {
                "200": {
                    "description": "Subscription details",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/SignalSubscription"
                            },
                        },
                    },
                },
                "404": {
                    "description": "Subscription not found",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
        "put": {
            "summary": "Update subscription",
            "description": "Update delivery channels, filters, or active status for a subscription.",
            "operationId": "updateSubscription",
            "tags": ["Signal Subscriptions"],
            "parameters": [
                {
                    "name": "subscription_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
            ],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "delivery_channels": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "webhook_url": {"type": "string", "format": "uri"},
                                "filters": {
                                    "$ref": "#/components/schemas/SignalFilter"
                                },
                                "active": {"type": "boolean"},
                            },
                        },
                    },
                },
            },
            "responses": {
                "200": {
                    "description": "Updated subscription",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/SignalSubscription"
                            },
                        },
                    },
                },
            },
        },
        "delete": {
            "summary": "Delete subscription",
            "description": "Permanently remove a signal subscription.",
            "operationId": "deleteSubscription",
            "tags": ["Signal Subscriptions"],
            "parameters": [
                {
                    "name": "subscription_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
            ],
            "responses": {
                "204": {"description": "Subscription deleted"},
            },
        },
    },
    "/api/v1/signals/subscriptions/{subscription_id}/deliveries": {
        "get": {
            "summary": "List delivery logs",
            "description": "View delivery history for a subscription including status and errors.",
            "operationId": "listDeliveryLogs",
            "tags": ["Signal Subscriptions"],
            "parameters": [
                {
                    "name": "subscription_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
                {
                    "name": "status",
                    "in": "query",
                    "schema": {
                        "type": "string",
                        "enum": ["delivered", "failed", "pending", "retrying"],
                    },
                },
                {
                    "name": "limit",
                    "in": "query",
                    "schema": {"type": "integer", "default": 50},
                },
            ],
            "responses": {
                "200": {
                    "description": "Delivery logs",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/CollectionResponse"
                            },
                        },
                    },
                },
            },
        },
    },
    "/api/v1/signals/subscriptions/{subscription_id}/test": {
        "post": {
            "summary": "Send test signal",
            "description": "Send a test signal through the subscription's delivery channels to verify connectivity.",
            "operationId": "testSubscription",
            "tags": ["Signal Subscriptions"],
            "parameters": [
                {
                    "name": "subscription_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
            ],
            "responses": {
                "200": {
                    "description": "Test delivery results per channel",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "results": {
                                        "type": "object",
                                        "additionalProperties": {
                                            "type": "object",
                                            "properties": {
                                                "success": {"type": "boolean"},
                                                "message": {"type": "string"},
                                            },
                                        },
                                    },
                                },
                                "example": {
                                    "results": {
                                        "webhook": {
                                            "success": True,
                                            "message": "200 OK",
                                        },
                                        "telegram": {
                                            "success": True,
                                            "message": "Message sent",
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
