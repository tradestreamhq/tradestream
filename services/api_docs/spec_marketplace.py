"""Strategy Marketplace API endpoints and schemas for the OpenAPI spec."""

MARKETPLACE_TAGS = [
    {
        "name": "Marketplace",
        "description": "Browse, purchase, and publish trading strategies",
    },
    {
        "name": "Marketplace Reviews",
        "description": "Strategy ratings and reviews",
    },
]

MARKETPLACE_SCHEMAS = {
    "MarketplaceListing": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "strategy_id": {"type": "string", "format": "uuid"},
            "name": {"type": "string", "example": "RSI Mean Reversion Pro"},
            "description": {"type": "string"},
            "author": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "format": "uuid"},
                    "display_name": {"type": "string", "example": "AlgoTrader99"},
                    "verified": {"type": "boolean"},
                },
            },
            "category": {
                "type": "string",
                "enum": [
                    "trend_following",
                    "mean_reversion",
                    "momentum",
                    "volatility",
                    "arbitrage",
                    "multi_strategy",
                ],
                "example": "mean_reversion",
            },
            "pricing": {"$ref": "#/components/schemas/ListingPricing"},
            "performance": {"$ref": "#/components/schemas/ListingPerformance"},
            "instruments": {
                "type": "array",
                "items": {"type": "string"},
                "example": ["BTC/USD", "ETH/USD"],
            },
            "timeframes": {
                "type": "array",
                "items": {"type": "string"},
                "example": ["4h", "1d"],
            },
            "subscriber_count": {"type": "integer", "example": 247},
            "rating": {
                "type": "number",
                "format": "double",
                "minimum": 0,
                "maximum": 5,
                "example": 4.3,
            },
            "review_count": {"type": "integer", "example": 38},
            "status": {
                "type": "string",
                "enum": ["draft", "pending_review", "published", "suspended"],
            },
            "published_at": {"type": "string", "format": "date-time"},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "example": ["crypto", "swing-trading", "low-risk"],
            },
        },
        "required": ["id", "strategy_id", "name", "category", "pricing"],
    },
    "ListingPricing": {
        "type": "object",
        "properties": {
            "model": {
                "type": "string",
                "enum": ["free", "one_time", "monthly", "annual"],
                "example": "monthly",
            },
            "price_cents": {
                "type": "integer",
                "description": "Price in cents (USD)",
                "example": 2999,
            },
            "trial_days": {
                "type": "integer",
                "description": "Free trial period in days (0 = no trial)",
                "example": 7,
            },
            "currency": {"type": "string", "example": "USD"},
        },
        "required": ["model"],
    },
    "ListingPerformance": {
        "type": "object",
        "description": "Verified backtest and live performance metrics",
        "properties": {
            "sharpe_ratio": {"type": "number", "format": "double", "example": 1.85},
            "total_return_pct": {"type": "number", "format": "double", "example": 42.3},
            "max_drawdown_pct": {
                "type": "number",
                "format": "double",
                "example": -12.5,
            },
            "win_rate": {"type": "number", "format": "double", "example": 0.62},
            "total_trades": {"type": "integer", "example": 312},
            "avg_trade_duration_hours": {
                "type": "number",
                "format": "double",
                "example": 18.5,
            },
            "profit_factor": {"type": "number", "format": "double", "example": 1.73},
            "backtest_period_start": {"type": "string", "format": "date"},
            "backtest_period_end": {"type": "string", "format": "date"},
            "live_since": {"type": "string", "format": "date"},
        },
    },
    "CreateListingRequest": {
        "type": "object",
        "properties": {
            "strategy_id": {"type": "string", "format": "uuid"},
            "name": {"type": "string", "maxLength": 100},
            "description": {"type": "string", "maxLength": 5000},
            "category": {
                "type": "string",
                "enum": [
                    "trend_following",
                    "mean_reversion",
                    "momentum",
                    "volatility",
                    "arbitrage",
                    "multi_strategy",
                ],
            },
            "pricing": {"$ref": "#/components/schemas/ListingPricing"},
            "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
        },
        "required": ["strategy_id", "name", "category", "pricing"],
    },
    "MarketplaceReview": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "listing_id": {"type": "string", "format": "uuid"},
            "user_id": {"type": "string", "format": "uuid"},
            "rating": {"type": "integer", "minimum": 1, "maximum": 5, "example": 4},
            "title": {"type": "string", "example": "Great strategy for crypto"},
            "body": {"type": "string"},
            "verified_purchase": {"type": "boolean"},
            "created_at": {"type": "string", "format": "date-time"},
        },
    },
    "CreateReviewRequest": {
        "type": "object",
        "properties": {
            "rating": {"type": "integer", "minimum": 1, "maximum": 5},
            "title": {"type": "string", "maxLength": 200},
            "body": {"type": "string", "maxLength": 2000},
        },
        "required": ["rating"],
    },
    "LeaderboardEntry": {
        "type": "object",
        "properties": {
            "rank": {"type": "integer", "example": 1},
            "listing": {"$ref": "#/components/schemas/MarketplaceListing"},
            "period_return_pct": {
                "type": "number",
                "format": "double",
                "example": 15.3,
            },
            "period_sharpe": {"type": "number", "format": "double", "example": 2.1},
        },
    },
}

MARKETPLACE_PATHS = {
    "/api/v1/marketplace/listings": {
        "get": {
            "summary": "Browse marketplace listings",
            "description": (
                "Search and filter strategy listings in the marketplace. "
                "Supports filtering by category, price range, performance metrics, and instruments."
            ),
            "operationId": "listMarketplaceListings",
            "tags": ["Marketplace"],
            "parameters": [
                {
                    "name": "category",
                    "in": "query",
                    "schema": {
                        "type": "string",
                        "enum": [
                            "trend_following",
                            "mean_reversion",
                            "momentum",
                            "volatility",
                            "arbitrage",
                            "multi_strategy",
                        ],
                    },
                },
                {
                    "name": "instrument",
                    "in": "query",
                    "schema": {"type": "string"},
                    "description": "Filter by supported instrument",
                },
                {
                    "name": "min_sharpe",
                    "in": "query",
                    "schema": {"type": "number"},
                    "description": "Minimum Sharpe ratio",
                },
                {
                    "name": "max_price_cents",
                    "in": "query",
                    "schema": {"type": "integer"},
                    "description": "Maximum monthly price in cents",
                },
                {
                    "name": "pricing_model",
                    "in": "query",
                    "schema": {
                        "type": "string",
                        "enum": ["free", "one_time", "monthly", "annual"],
                    },
                },
                {
                    "name": "sort_by",
                    "in": "query",
                    "schema": {
                        "type": "string",
                        "enum": ["rating", "subscribers", "return", "sharpe", "newest"],
                        "default": "rating",
                    },
                },
                {
                    "name": "search",
                    "in": "query",
                    "schema": {"type": "string"},
                    "description": "Full-text search across name, description, tags",
                },
                {
                    "name": "limit",
                    "in": "query",
                    "schema": {"type": "integer", "default": 20, "maximum": 100},
                },
                {
                    "name": "offset",
                    "in": "query",
                    "schema": {"type": "integer", "default": 0},
                },
            ],
            "responses": {
                "200": {
                    "description": "Paginated marketplace listings",
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
            "summary": "Create marketplace listing",
            "description": "Publish a strategy to the marketplace. The strategy must pass validation before it can be listed.",
            "operationId": "createMarketplaceListing",
            "tags": ["Marketplace"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/CreateListingRequest"},
                    },
                },
            },
            "responses": {
                "201": {
                    "description": "Listing created (pending review)",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/MarketplaceListing"
                            },
                        },
                    },
                },
                "400": {
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
    "/api/v1/marketplace/listings/{listing_id}": {
        "get": {
            "summary": "Get listing details",
            "description": "Retrieve full details for a marketplace listing including performance metrics.",
            "operationId": "getMarketplaceListing",
            "tags": ["Marketplace"],
            "parameters": [
                {
                    "name": "listing_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
            ],
            "responses": {
                "200": {
                    "description": "Listing details",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/MarketplaceListing"
                            },
                        },
                    },
                },
                "404": {
                    "description": "Listing not found",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
        "put": {
            "summary": "Update listing",
            "description": "Update listing description, pricing, or tags. Cannot change the underlying strategy.",
            "operationId": "updateMarketplaceListing",
            "tags": ["Marketplace"],
            "parameters": [
                {
                    "name": "listing_id",
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
                                "description": {"type": "string"},
                                "pricing": {
                                    "$ref": "#/components/schemas/ListingPricing"
                                },
                                "tags": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                },
            },
            "responses": {
                "200": {
                    "description": "Updated listing",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/MarketplaceListing"
                            },
                        },
                    },
                },
            },
        },
        "delete": {
            "summary": "Unpublish listing",
            "description": "Remove a listing from the marketplace. Existing subscribers retain access until their subscription period ends.",
            "operationId": "deleteMarketplaceListing",
            "tags": ["Marketplace"],
            "parameters": [
                {
                    "name": "listing_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
            ],
            "responses": {
                "204": {"description": "Listing removed"},
            },
        },
    },
    "/api/v1/marketplace/listings/{listing_id}/subscribe": {
        "post": {
            "summary": "Subscribe to listing",
            "description": "Subscribe to a marketplace strategy listing. Creates a Stripe checkout session for paid listings.",
            "operationId": "subscribeToListing",
            "tags": ["Marketplace"],
            "parameters": [
                {
                    "name": "listing_id",
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
                                    "items": {
                                        "type": "string",
                                        "enum": [
                                            "webhook",
                                            "email",
                                            "telegram",
                                            "discord",
                                        ],
                                    },
                                },
                                "webhook_url": {"type": "string", "format": "uri"},
                            },
                            "required": ["delivery_channels"],
                        },
                    },
                },
            },
            "responses": {
                "201": {
                    "description": "Subscription created (or checkout URL for paid listings)",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "subscription_id": {
                                        "type": "string",
                                        "format": "uuid",
                                    },
                                    "checkout_url": {
                                        "type": "string",
                                        "format": "uri",
                                        "description": "Stripe checkout URL (paid listings only)",
                                    },
                                    "status": {
                                        "type": "string",
                                        "enum": ["active", "pending_payment"],
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "/api/v1/marketplace/listings/{listing_id}/reviews": {
        "get": {
            "summary": "List reviews for a listing",
            "description": "Get paginated reviews for a marketplace listing.",
            "operationId": "listListingReviews",
            "tags": ["Marketplace Reviews"],
            "parameters": [
                {
                    "name": "listing_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
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
                    "description": "Paginated reviews",
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
            "summary": "Submit a review",
            "description": "Submit a rating and review for a marketplace listing. Requires an active subscription.",
            "operationId": "createListingReview",
            "tags": ["Marketplace Reviews"],
            "parameters": [
                {
                    "name": "listing_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
            ],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/CreateReviewRequest"},
                    },
                },
            },
            "responses": {
                "201": {
                    "description": "Review submitted",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/MarketplaceReview"
                            },
                        },
                    },
                },
                "403": {
                    "description": "Must be a subscriber to review",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/marketplace/leaderboard": {
        "get": {
            "summary": "Get marketplace leaderboard",
            "description": "Top performing strategies ranked by returns, Sharpe ratio, or subscriber count.",
            "operationId": "getMarketplaceLeaderboard",
            "tags": ["Marketplace"],
            "parameters": [
                {
                    "name": "period",
                    "in": "query",
                    "schema": {
                        "type": "string",
                        "enum": ["7d", "30d", "90d", "1y", "all"],
                        "default": "30d",
                    },
                },
                {
                    "name": "sort_by",
                    "in": "query",
                    "schema": {
                        "type": "string",
                        "enum": ["return", "sharpe", "subscribers"],
                        "default": "return",
                    },
                },
                {
                    "name": "category",
                    "in": "query",
                    "schema": {"type": "string"},
                },
                {
                    "name": "limit",
                    "in": "query",
                    "schema": {"type": "integer", "default": 25, "maximum": 100},
                },
            ],
            "responses": {
                "200": {
                    "description": "Leaderboard entries",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {
                                        "type": "array",
                                        "items": {
                                            "$ref": "#/components/schemas/LeaderboardEntry"
                                        },
                                    },
                                    "period": {"type": "string"},
                                    "updated_at": {
                                        "type": "string",
                                        "format": "date-time",
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
