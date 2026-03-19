"""User Management and API Key endpoints and schemas."""

USERS_TAGS = [
    {
        "name": "Users",
        "description": "User registration, profile, and account management",
    },
    {
        "name": "API Keys",
        "description": "API key creation, rotation, and management",
    },
    {
        "name": "Notifications",
        "description": "Notification preferences and delivery configuration",
    },
]

USERS_SCHEMAS = {
    "User": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "email": {"type": "string", "format": "email", "example": "trader@example.com"},
            "display_name": {"type": "string", "example": "AlgoTrader99"},
            "role": {
                "type": "string",
                "enum": ["user", "publisher", "admin"],
                "example": "user",
            },
            "plan": {"type": "string", "enum": ["free", "starter", "pro", "enterprise"]},
            "email_verified": {"type": "boolean"},
            "two_factor_enabled": {"type": "boolean"},
            "timezone": {"type": "string", "example": "America/New_York"},
            "created_at": {"type": "string", "format": "date-time"},
            "last_login_at": {"type": "string", "format": "date-time"},
        },
    },
    "RegisterRequest": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "format": "email"},
            "password": {"type": "string", "minLength": 8},
            "display_name": {"type": "string", "minLength": 2, "maxLength": 50},
        },
        "required": ["email", "password"],
    },
    "LoginRequest": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "format": "email"},
            "password": {"type": "string"},
            "totp_code": {
                "type": "string",
                "description": "TOTP code for 2FA (required if 2FA is enabled)",
            },
        },
        "required": ["email", "password"],
    },
    "AuthTokens": {
        "type": "object",
        "properties": {
            "access_token": {"type": "string", "description": "JWT access token (15 min TTL)"},
            "refresh_token": {"type": "string", "description": "Refresh token (30 day TTL)"},
            "token_type": {"type": "string", "example": "Bearer"},
            "expires_in": {"type": "integer", "description": "Access token TTL in seconds", "example": 900},
        },
    },
    "UpdateProfileRequest": {
        "type": "object",
        "properties": {
            "display_name": {"type": "string"},
            "timezone": {"type": "string"},
            "avatar_url": {"type": "string", "format": "uri"},
        },
    },
    "ApiKey": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "name": {"type": "string", "example": "Production Webhook"},
            "prefix": {
                "type": "string",
                "description": "First 8 characters of the key for identification",
                "example": "ts_live_",
            },
            "scopes": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "signals:read",
                        "signals:write",
                        "strategies:read",
                        "strategies:write",
                        "portfolio:read",
                        "backtests:run",
                        "marketplace:read",
                        "marketplace:publish",
                    ],
                },
                "example": ["signals:read", "portfolio:read"],
            },
            "last_used_at": {"type": "string", "format": "date-time"},
            "expires_at": {
                "type": "string",
                "format": "date-time",
                "description": "Key expiration (null = never expires)",
            },
            "created_at": {"type": "string", "format": "date-time"},
        },
    },
    "CreateApiKeyRequest": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "example": "My Trading Bot"},
            "scopes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Permission scopes for this key",
            },
            "expires_in_days": {
                "type": "integer",
                "description": "Key TTL in days (null = never expires)",
                "example": 90,
            },
        },
        "required": ["name", "scopes"],
    },
    "CreateApiKeyResponse": {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "Full API key — shown only once at creation time",
                "example": "ts_live_sk_abc123def456ghi789jkl012mno345pqr678",
            },
            "api_key": {"$ref": "#/components/schemas/ApiKey"},
        },
    },
    "NotificationPreferences": {
        "type": "object",
        "properties": {
            "email_enabled": {"type": "boolean", "example": True},
            "telegram_enabled": {"type": "boolean", "example": True},
            "telegram_chat_id": {"type": "string"},
            "discord_enabled": {"type": "boolean", "example": False},
            "discord_webhook_url": {"type": "string", "format": "uri"},
            "signal_notifications": {"type": "boolean", "example": True},
            "opportunity_notifications": {"type": "boolean", "example": True},
            "min_opportunity_tier": {
                "type": "string",
                "enum": ["S", "A", "B", "C"],
                "example": "B",
            },
            "billing_notifications": {"type": "boolean", "example": True},
            "weekly_digest": {"type": "boolean", "example": True},
        },
    },
}

USERS_PATHS = {
    "/api/v1/auth/register": {
        "post": {
            "summary": "Register new user",
            "description": "Create a new TradeStream account. Sends a verification email.",
            "operationId": "registerUser",
            "tags": ["Users"],
            "security": [],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/RegisterRequest"},
                        "example": {
                            "email": "trader@example.com",
                            "password": "secureP@ss123",
                            "display_name": "AlgoTrader99",
                        },
                    },
                },
            },
            "responses": {
                "201": {
                    "description": "Account created — verification email sent",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/User"},
                        },
                    },
                },
                "409": {
                    "description": "Email already registered",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/auth/login": {
        "post": {
            "summary": "Login",
            "description": "Authenticate with email/password. Returns JWT access and refresh tokens.",
            "operationId": "loginUser",
            "tags": ["Users"],
            "security": [],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/LoginRequest"},
                    },
                },
            },
            "responses": {
                "200": {
                    "description": "Authentication successful",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/AuthTokens"},
                            "example": {
                                "access_token": "eyJhbGciOiJSUzI1NiIs...",
                                "refresh_token": "rt_abc123...",
                                "token_type": "Bearer",
                                "expires_in": 900,
                            },
                        },
                    },
                },
                "401": {
                    "description": "Invalid credentials",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/auth/refresh": {
        "post": {
            "summary": "Refresh access token",
            "description": "Exchange a refresh token for a new access token.",
            "operationId": "refreshToken",
            "tags": ["Users"],
            "security": [],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "refresh_token": {"type": "string"},
                            },
                            "required": ["refresh_token"],
                        },
                    },
                },
            },
            "responses": {
                "200": {
                    "description": "New tokens",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/AuthTokens"},
                        },
                    },
                },
                "401": {
                    "description": "Invalid or expired refresh token",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/auth/logout": {
        "post": {
            "summary": "Logout",
            "description": "Revoke the current refresh token.",
            "operationId": "logoutUser",
            "tags": ["Users"],
            "responses": {
                "204": {"description": "Logged out"},
            },
        },
    },
    "/api/v1/users/me": {
        "get": {
            "summary": "Get current user profile",
            "description": "Get the authenticated user's profile information.",
            "operationId": "getCurrentUser",
            "tags": ["Users"],
            "responses": {
                "200": {
                    "description": "User profile",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/User"},
                        },
                    },
                },
            },
        },
        "put": {
            "summary": "Update user profile",
            "description": "Update display name, timezone, or avatar.",
            "operationId": "updateCurrentUser",
            "tags": ["Users"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/UpdateProfileRequest"},
                    },
                },
            },
            "responses": {
                "200": {
                    "description": "Updated profile",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/User"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/users/me/change-password": {
        "post": {
            "summary": "Change password",
            "description": "Change the authenticated user's password.",
            "operationId": "changePassword",
            "tags": ["Users"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "current_password": {"type": "string"},
                                "new_password": {"type": "string", "minLength": 8},
                            },
                            "required": ["current_password", "new_password"],
                        },
                    },
                },
            },
            "responses": {
                "204": {"description": "Password changed"},
                "400": {
                    "description": "Current password incorrect or new password too weak",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/api-keys": {
        "get": {
            "summary": "List API keys",
            "description": "List all API keys for the authenticated user. Keys are shown with prefix only (not the full secret).",
            "operationId": "listApiKeys",
            "tags": ["API Keys"],
            "responses": {
                "200": {
                    "description": "API key list",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/ApiKey"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "post": {
            "summary": "Create API key",
            "description": (
                "Create a new API key with specified scopes. The full key is returned only once in the response — "
                "store it securely."
            ),
            "operationId": "createApiKey",
            "tags": ["API Keys"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/CreateApiKeyRequest"},
                        "example": {
                            "name": "Production Webhook",
                            "scopes": ["signals:read", "portfolio:read"],
                            "expires_in_days": 90,
                        },
                    },
                },
            },
            "responses": {
                "201": {
                    "description": "API key created — full key shown only once",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/CreateApiKeyResponse"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/api-keys/{key_id}": {
        "delete": {
            "summary": "Revoke API key",
            "description": "Permanently revoke an API key. This action cannot be undone.",
            "operationId": "revokeApiKey",
            "tags": ["API Keys"],
            "parameters": [
                {
                    "name": "key_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
            ],
            "responses": {
                "204": {"description": "Key revoked"},
                "404": {
                    "description": "Key not found",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/api-keys/{key_id}/rotate": {
        "post": {
            "summary": "Rotate API key",
            "description": "Generate a new secret for an existing API key. The old key is immediately invalidated.",
            "operationId": "rotateApiKey",
            "tags": ["API Keys"],
            "parameters": [
                {
                    "name": "key_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
            ],
            "responses": {
                "200": {
                    "description": "New key secret — shown only once",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/CreateApiKeyResponse"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/users/me/notifications": {
        "get": {
            "summary": "Get notification preferences",
            "description": "Get the authenticated user's notification settings.",
            "operationId": "getNotificationPreferences",
            "tags": ["Notifications"],
            "responses": {
                "200": {
                    "description": "Notification preferences",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/NotificationPreferences"},
                        },
                    },
                },
            },
        },
        "put": {
            "summary": "Update notification preferences",
            "description": "Update notification channels and preferences.",
            "operationId": "updateNotificationPreferences",
            "tags": ["Notifications"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/NotificationPreferences"},
                    },
                },
            },
            "responses": {
                "200": {
                    "description": "Updated preferences",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/NotificationPreferences"},
                        },
                    },
                },
            },
        },
    },
}
