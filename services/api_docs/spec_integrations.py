"""Integration API endpoints — TradingView, Telegram, Discord, Webhooks."""

INTEGRATIONS_TAGS = [
    {
        "name": "TradingView",
        "description": "TradingView webhook alerts and Pine Script integration",
    },
    {
        "name": "Telegram",
        "description": "Telegram bot commands and signal delivery",
    },
    {
        "name": "Discord",
        "description": "Discord webhook integration for signal delivery",
    },
    {
        "name": "Webhooks",
        "description": "Outbound webhook configuration and management",
    },
]

INTEGRATIONS_SCHEMAS = {
    "TradingViewAlert": {
        "type": "object",
        "description": (
            "TradingView webhook alert payload. Configure your TradingView alert "
            "to POST JSON to your TradeStream webhook URL."
        ),
        "properties": {
            "ticker": {"type": "string", "example": "BTCUSD"},
            "exchange": {"type": "string", "example": "BINANCE"},
            "action": {
                "type": "string",
                "enum": ["buy", "sell", "close"],
                "example": "buy",
            },
            "price": {"type": "number", "format": "double", "example": 67500.00},
            "volume": {"type": "number", "format": "double"},
            "timeframe": {"type": "string", "example": "240"},
            "strategy_name": {"type": "string", "example": "RSI_Mean_Reversion"},
            "comment": {"type": "string", "description": "Pine Script alert message"},
            "timestamp": {"type": "string", "format": "date-time"},
        },
        "required": ["ticker", "action"],
    },
    "TradingViewConfig": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "webhook_url": {
                "type": "string",
                "format": "uri",
                "description": "Your unique TradingView webhook URL",
                "example": "https://api.tradestream.io/api/v1/integrations/tradingview/webhook/abc123",
            },
            "webhook_secret": {
                "type": "string",
                "description": "Secret token for authenticating TradingView webhooks",
            },
            "instrument_mapping": {
                "type": "object",
                "description": "Map TradingView ticker names to TradeStream instruments",
                "additionalProperties": {"type": "string"},
                "example": {"BTCUSD": "BTC/USD", "ETHUSD": "ETH/USD"},
            },
            "auto_subscribe": {
                "type": "boolean",
                "description": "Automatically create signal subscriptions for incoming alerts",
            },
            "enabled": {"type": "boolean"},
        },
    },
    "TelegramConfig": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "chat_id": {"type": "string", "description": "Telegram chat ID for notifications"},
            "bot_connected": {"type": "boolean"},
            "verification_code": {
                "type": "string",
                "description": "Code to send to @TradeStreamBot to link your account",
            },
            "signal_format": {
                "type": "string",
                "enum": ["compact", "detailed", "custom"],
                "description": "Signal message format",
                "example": "detailed",
            },
            "enabled": {"type": "boolean"},
        },
    },
    "DiscordConfig": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "webhook_url": {
                "type": "string",
                "format": "uri",
                "description": "Discord webhook URL from your server settings",
            },
            "channel_name": {"type": "string", "example": "#trading-signals"},
            "embed_format": {
                "type": "boolean",
                "description": "Use Discord rich embeds for signals",
                "example": True,
            },
            "mention_role_id": {
                "type": "string",
                "description": "Discord role ID to mention on high-tier signals",
            },
            "enabled": {"type": "boolean"},
        },
    },
    "WebhookConfig": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "name": {"type": "string", "example": "Production Signal Handler"},
            "url": {"type": "string", "format": "uri", "example": "https://your-app.com/signals"},
            "secret": {
                "type": "string",
                "description": "HMAC-SHA256 signing secret for payload verification",
            },
            "events": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "signal.created",
                        "signal.expired",
                        "opportunity.created",
                        "backtest.completed",
                        "subscription.changed",
                    ],
                },
                "example": ["signal.created", "opportunity.created"],
            },
            "headers": {
                "type": "object",
                "description": "Custom headers to include in webhook requests",
                "additionalProperties": {"type": "string"},
            },
            "retry_policy": {
                "type": "object",
                "properties": {
                    "max_retries": {"type": "integer", "default": 3},
                    "backoff_seconds": {"type": "integer", "default": 30},
                },
            },
            "enabled": {"type": "boolean"},
            "last_delivery_at": {"type": "string", "format": "date-time"},
            "last_status_code": {"type": "integer"},
        },
    },
    "CreateWebhookRequest": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "url": {"type": "string", "format": "uri"},
            "events": {
                "type": "array",
                "items": {"type": "string"},
            },
            "headers": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["name", "url", "events"],
    },
    "WebhookDelivery": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "webhook_id": {"type": "string", "format": "uuid"},
            "event_type": {"type": "string"},
            "payload": {"type": "object"},
            "response_code": {"type": "integer"},
            "response_body": {"type": "string"},
            "duration_ms": {"type": "integer"},
            "attempt": {"type": "integer"},
            "status": {"type": "string", "enum": ["success", "failed", "pending"]},
            "delivered_at": {"type": "string", "format": "date-time"},
        },
    },
    "WebhookPayloadExample": {
        "type": "object",
        "description": "Example webhook payload sent to your endpoint",
        "properties": {
            "event": {"type": "string", "example": "signal.created"},
            "timestamp": {"type": "string", "format": "date-time"},
            "data": {
                "type": "object",
                "example": {
                    "signal_id": "sig_abc123",
                    "instrument": "BTC/USD",
                    "direction": "BUY",
                    "strength": 0.85,
                    "entry_price": 67500.00,
                    "stop_loss": 66000.00,
                    "take_profit": 70000.00,
                },
            },
        },
    },
}

INTEGRATIONS_PATHS = {
    # --- TradingView ---
    "/api/v1/integrations/tradingview": {
        "get": {
            "summary": "Get TradingView integration config",
            "description": "Retrieve your TradingView webhook configuration including the unique webhook URL.",
            "operationId": "getTradingViewConfig",
            "tags": ["TradingView"],
            "responses": {
                "200": {
                    "description": "TradingView configuration",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/TradingViewConfig"},
                        },
                    },
                },
            },
        },
        "put": {
            "summary": "Update TradingView config",
            "description": "Update instrument mappings and auto-subscribe settings.",
            "operationId": "updateTradingViewConfig",
            "tags": ["TradingView"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "instrument_mapping": {
                                    "type": "object",
                                    "additionalProperties": {"type": "string"},
                                },
                                "auto_subscribe": {"type": "boolean"},
                                "enabled": {"type": "boolean"},
                            },
                        },
                    },
                },
            },
            "responses": {
                "200": {
                    "description": "Updated config",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/TradingViewConfig"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/integrations/tradingview/webhook/{webhook_token}": {
        "post": {
            "summary": "TradingView webhook receiver",
            "description": (
                "Receives alerts from TradingView. Configure this URL in your TradingView alert. "
                "The webhook_token in the URL authenticates the request."
            ),
            "operationId": "receiveTradingViewAlert",
            "tags": ["TradingView"],
            "security": [],
            "parameters": [
                {
                    "name": "webhook_token",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                    "description": "Unique webhook authentication token",
                },
            ],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/TradingViewAlert"},
                        "example": {
                            "ticker": "BTCUSD",
                            "exchange": "BINANCE",
                            "action": "buy",
                            "price": 67500.00,
                            "timeframe": "240",
                            "strategy_name": "RSI_Mean_Reversion",
                            "comment": "RSI crossed below 30 on 4h chart",
                        },
                    },
                },
            },
            "responses": {
                "200": {
                    "description": "Alert processed",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "signal_id": {"type": "string"},
                                    "status": {"type": "string", "example": "processed"},
                                },
                            },
                        },
                    },
                },
                "401": {
                    "description": "Invalid webhook token",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/integrations/tradingview/pine-template": {
        "get": {
            "summary": "Get Pine Script template",
            "description": "Download a Pine Script template pre-configured with your webhook URL for easy TradingView setup.",
            "operationId": "getPineScriptTemplate",
            "tags": ["TradingView"],
            "parameters": [
                {
                    "name": "strategy_type",
                    "in": "query",
                    "schema": {
                        "type": "string",
                        "enum": ["rsi", "macd", "ema_crossover", "custom"],
                        "default": "custom",
                    },
                },
            ],
            "responses": {
                "200": {
                    "description": "Pine Script template",
                    "content": {
                        "text/plain": {
                            "schema": {"type": "string"},
                        },
                    },
                },
            },
        },
    },
    # --- Telegram ---
    "/api/v1/integrations/telegram": {
        "get": {
            "summary": "Get Telegram integration config",
            "description": "Get Telegram bot connection status and configuration.",
            "operationId": "getTelegramConfig",
            "tags": ["Telegram"],
            "responses": {
                "200": {
                    "description": "Telegram configuration",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/TelegramConfig"},
                        },
                    },
                },
            },
        },
        "put": {
            "summary": "Update Telegram config",
            "description": "Update Telegram signal format and enabled status.",
            "operationId": "updateTelegramConfig",
            "tags": ["Telegram"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "signal_format": {
                                    "type": "string",
                                    "enum": ["compact", "detailed", "custom"],
                                },
                                "enabled": {"type": "boolean"},
                            },
                        },
                    },
                },
            },
            "responses": {
                "200": {
                    "description": "Updated config",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/TelegramConfig"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/integrations/telegram/connect": {
        "post": {
            "summary": "Generate Telegram connection code",
            "description": (
                "Generate a verification code. Send this code to @TradeStreamBot on Telegram "
                "to link your account."
            ),
            "operationId": "connectTelegram",
            "tags": ["Telegram"],
            "responses": {
                "200": {
                    "description": "Connection code generated",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "verification_code": {
                                        "type": "string",
                                        "example": "TS-482910",
                                    },
                                    "bot_username": {
                                        "type": "string",
                                        "example": "@TradeStreamBot",
                                    },
                                    "instructions": {"type": "string"},
                                    "expires_in_minutes": {"type": "integer", "example": 10},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "/api/v1/integrations/telegram/disconnect": {
        "post": {
            "summary": "Disconnect Telegram",
            "description": "Unlink your Telegram account from TradeStream.",
            "operationId": "disconnectTelegram",
            "tags": ["Telegram"],
            "responses": {
                "204": {"description": "Telegram disconnected"},
            },
        },
    },
    "/api/v1/integrations/telegram/test": {
        "post": {
            "summary": "Send test message to Telegram",
            "description": "Send a test signal message to your connected Telegram account.",
            "operationId": "testTelegram",
            "tags": ["Telegram"],
            "responses": {
                "200": {
                    "description": "Test message sent",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean"},
                                    "message_id": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    # --- Discord ---
    "/api/v1/integrations/discord": {
        "get": {
            "summary": "Get Discord integration config",
            "description": "Get Discord webhook configuration.",
            "operationId": "getDiscordConfig",
            "tags": ["Discord"],
            "responses": {
                "200": {
                    "description": "Discord configuration",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/DiscordConfig"},
                        },
                    },
                },
            },
        },
        "put": {
            "summary": "Update Discord config",
            "description": "Set or update the Discord webhook URL and formatting options.",
            "operationId": "updateDiscordConfig",
            "tags": ["Discord"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "webhook_url": {"type": "string", "format": "uri"},
                                "embed_format": {"type": "boolean"},
                                "mention_role_id": {"type": "string"},
                                "enabled": {"type": "boolean"},
                            },
                        },
                    },
                },
            },
            "responses": {
                "200": {
                    "description": "Updated config",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/DiscordConfig"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/integrations/discord/test": {
        "post": {
            "summary": "Send test message to Discord",
            "description": "Send a test signal embed to your Discord channel.",
            "operationId": "testDiscord",
            "tags": ["Discord"],
            "responses": {
                "200": {
                    "description": "Test message sent",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean"},
                                    "message": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    # --- Outbound Webhooks ---
    "/api/v1/webhooks": {
        "get": {
            "summary": "List webhook endpoints",
            "description": "List all configured outbound webhook endpoints.",
            "operationId": "listWebhooks",
            "tags": ["Webhooks"],
            "responses": {
                "200": {
                    "description": "Webhook list",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/WebhookConfig"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "post": {
            "summary": "Create webhook endpoint",
            "description": (
                "Register a new outbound webhook endpoint. A signing secret is generated automatically "
                "for HMAC-SHA256 payload verification."
            ),
            "operationId": "createWebhook",
            "tags": ["Webhooks"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/CreateWebhookRequest"},
                        "example": {
                            "name": "Production Signal Handler",
                            "url": "https://your-app.com/webhooks/tradestream",
                            "events": ["signal.created", "opportunity.created"],
                        },
                    },
                },
            },
            "responses": {
                "201": {
                    "description": "Webhook created — secret shown only once",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/WebhookConfig"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/webhooks/{webhook_id}": {
        "get": {
            "summary": "Get webhook details",
            "description": "Get configuration and recent delivery status for a webhook endpoint.",
            "operationId": "getWebhook",
            "tags": ["Webhooks"],
            "parameters": [
                {
                    "name": "webhook_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
            ],
            "responses": {
                "200": {
                    "description": "Webhook details",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/WebhookConfig"},
                        },
                    },
                },
            },
        },
        "put": {
            "summary": "Update webhook endpoint",
            "description": "Update webhook URL, events, or enabled status.",
            "operationId": "updateWebhook",
            "tags": ["Webhooks"],
            "parameters": [
                {
                    "name": "webhook_id",
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
                                "name": {"type": "string"},
                                "url": {"type": "string", "format": "uri"},
                                "events": {"type": "array", "items": {"type": "string"}},
                                "headers": {"type": "object", "additionalProperties": {"type": "string"}},
                                "enabled": {"type": "boolean"},
                            },
                        },
                    },
                },
            },
            "responses": {
                "200": {
                    "description": "Updated webhook",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/WebhookConfig"},
                        },
                    },
                },
            },
        },
        "delete": {
            "summary": "Delete webhook endpoint",
            "description": "Permanently delete a webhook endpoint.",
            "operationId": "deleteWebhook",
            "tags": ["Webhooks"],
            "parameters": [
                {
                    "name": "webhook_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
            ],
            "responses": {
                "204": {"description": "Webhook deleted"},
            },
        },
    },
    "/api/v1/webhooks/{webhook_id}/deliveries": {
        "get": {
            "summary": "List webhook deliveries",
            "description": "View delivery history for a webhook endpoint including request/response details.",
            "operationId": "listWebhookDeliveries",
            "tags": ["Webhooks"],
            "parameters": [
                {
                    "name": "webhook_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
                {
                    "name": "status",
                    "in": "query",
                    "schema": {"type": "string", "enum": ["success", "failed", "pending"]},
                },
                {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 20}},
            ],
            "responses": {
                "200": {
                    "description": "Delivery history",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/CollectionResponse"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/webhooks/{webhook_id}/test": {
        "post": {
            "summary": "Send test webhook",
            "description": "Send a test payload to the webhook endpoint to verify connectivity.",
            "operationId": "testWebhook",
            "tags": ["Webhooks"],
            "parameters": [
                {
                    "name": "webhook_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
            ],
            "responses": {
                "200": {
                    "description": "Test delivery result",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/WebhookDelivery"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/webhooks/{webhook_id}/secret/rotate": {
        "post": {
            "summary": "Rotate webhook signing secret",
            "description": "Generate a new HMAC-SHA256 signing secret. The old secret is immediately invalidated.",
            "operationId": "rotateWebhookSecret",
            "tags": ["Webhooks"],
            "parameters": [
                {
                    "name": "webhook_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
            ],
            "responses": {
                "200": {
                    "description": "New signing secret — shown only once",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "secret": {
                                        "type": "string",
                                        "description": "New HMAC-SHA256 signing secret",
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
