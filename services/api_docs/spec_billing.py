"""Billing and Subscription API endpoints and schemas for the OpenAPI spec."""

BILLING_TAGS = [
    {
        "name": "Billing",
        "description": "Subscription management, invoices, and payment methods (powered by Stripe)",
    },
    {
        "name": "Webhooks - Stripe",
        "description": "Stripe webhook event handling",
    },
]

BILLING_SCHEMAS = {
    "BillingAccount": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "user_id": {"type": "string", "format": "uuid"},
            "stripe_customer_id": {"type": "string", "example": "cus_abc123"},
            "plan": {
                "type": "string",
                "enum": ["free", "starter", "pro", "enterprise"],
                "example": "pro",
            },
            "status": {
                "type": "string",
                "enum": ["active", "past_due", "cancelled", "trialing"],
                "example": "active",
            },
            "current_period_start": {"type": "string", "format": "date-time"},
            "current_period_end": {"type": "string", "format": "date-time"},
            "cancel_at_period_end": {"type": "boolean"},
            "usage": {"$ref": "#/components/schemas/UsageMetrics"},
        },
    },
    "UsageMetrics": {
        "type": "object",
        "description": "Current billing period usage against plan limits",
        "properties": {
            "signals_delivered": {"type": "integer", "example": 1250},
            "signals_limit": {"type": "integer", "example": 5000},
            "api_calls": {"type": "integer", "example": 8432},
            "api_calls_limit": {"type": "integer", "example": 50000},
            "strategies_active": {"type": "integer", "example": 3},
            "strategies_limit": {"type": "integer", "example": 10},
            "backtests_run": {"type": "integer", "example": 15},
            "backtests_limit": {"type": "integer", "example": 100},
        },
    },
    "Plan": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "enum": ["free", "starter", "pro", "enterprise"]},
            "name": {"type": "string", "example": "Pro"},
            "price_monthly_cents": {"type": "integer", "example": 4999},
            "price_annual_cents": {"type": "integer", "example": 47988},
            "features": {
                "type": "object",
                "properties": {
                    "signals_per_month": {"type": "integer"},
                    "api_calls_per_month": {"type": "integer"},
                    "max_strategies": {"type": "integer"},
                    "backtests_per_month": {"type": "integer"},
                    "webhook_delivery": {"type": "boolean"},
                    "telegram_integration": {"type": "boolean"},
                    "discord_integration": {"type": "boolean"},
                    "tradingview_integration": {"type": "boolean"},
                    "priority_support": {"type": "boolean"},
                },
            },
        },
    },
    "Invoice": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "example": "inv_abc123"},
            "stripe_invoice_id": {"type": "string"},
            "amount_cents": {"type": "integer", "example": 4999},
            "currency": {"type": "string", "example": "USD"},
            "status": {
                "type": "string",
                "enum": ["draft", "open", "paid", "void", "uncollectible"],
            },
            "period_start": {"type": "string", "format": "date-time"},
            "period_end": {"type": "string", "format": "date-time"},
            "invoice_url": {"type": "string", "format": "uri"},
            "pdf_url": {"type": "string", "format": "uri"},
            "created_at": {"type": "string", "format": "date-time"},
        },
    },
    "PaymentMethod": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "type": {"type": "string", "enum": ["card", "bank_account"]},
            "card": {
                "type": "object",
                "properties": {
                    "brand": {"type": "string", "example": "visa"},
                    "last4": {"type": "string", "example": "4242"},
                    "exp_month": {"type": "integer", "example": 12},
                    "exp_year": {"type": "integer", "example": 2027},
                },
            },
            "is_default": {"type": "boolean"},
        },
    },
    "ChangePlanRequest": {
        "type": "object",
        "properties": {
            "plan": {
                "type": "string",
                "enum": ["free", "starter", "pro", "enterprise"],
            },
            "billing_cycle": {
                "type": "string",
                "enum": ["monthly", "annual"],
                "default": "monthly",
            },
        },
        "required": ["plan"],
    },
    "StripeWebhookEvent": {
        "type": "object",
        "description": "Stripe webhook event payload. Verified via Stripe-Signature header.",
        "properties": {
            "id": {"type": "string", "example": "evt_abc123"},
            "type": {
                "type": "string",
                "example": "invoice.payment_succeeded",
                "description": (
                    "Event types handled: checkout.session.completed, "
                    "invoice.payment_succeeded, invoice.payment_failed, "
                    "customer.subscription.updated, customer.subscription.deleted"
                ),
            },
            "data": {"type": "object"},
        },
    },
}

BILLING_PATHS = {
    "/api/v1/billing/account": {
        "get": {
            "summary": "Get billing account",
            "description": "Retrieve the authenticated user's billing account including plan, status, and usage.",
            "operationId": "getBillingAccount",
            "tags": ["Billing"],
            "responses": {
                "200": {
                    "description": "Billing account details",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/BillingAccount"},
                            "example": {
                                "id": "ba_abc123",
                                "plan": "pro",
                                "status": "active",
                                "current_period_end": "2026-04-19T00:00:00Z",
                                "usage": {
                                    "signals_delivered": 1250,
                                    "signals_limit": 5000,
                                    "api_calls": 8432,
                                    "api_calls_limit": 50000,
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "/api/v1/billing/plans": {
        "get": {
            "summary": "List available plans",
            "description": "Get all available subscription plans with features and pricing.",
            "operationId": "listPlans",
            "tags": ["Billing"],
            "security": [],
            "responses": {
                "200": {
                    "description": "Available plans",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "plans": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/Plan"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "/api/v1/billing/plan": {
        "put": {
            "summary": "Change subscription plan",
            "description": (
                "Upgrade or downgrade the subscription plan. Upgrades are prorated immediately. "
                "Downgrades take effect at the end of the current billing period."
            ),
            "operationId": "changePlan",
            "tags": ["Billing"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ChangePlanRequest"},
                        "example": {"plan": "pro", "billing_cycle": "annual"},
                    },
                },
            },
            "responses": {
                "200": {
                    "description": "Plan updated",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/BillingAccount"},
                        },
                    },
                },
                "400": {
                    "description": "Invalid plan change",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/billing/cancel": {
        "post": {
            "summary": "Cancel subscription",
            "description": "Cancel the active subscription. Access continues until the end of the current billing period.",
            "operationId": "cancelSubscription",
            "tags": ["Billing"],
            "responses": {
                "200": {
                    "description": "Cancellation confirmed",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "cancelled": {"type": "boolean", "example": True},
                                    "access_until": {"type": "string", "format": "date-time"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "/api/v1/billing/invoices": {
        "get": {
            "summary": "List invoices",
            "description": "Retrieve billing invoice history with pagination.",
            "operationId": "listInvoices",
            "tags": ["Billing"],
            "parameters": [
                {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 20}},
                {"name": "offset", "in": "query", "schema": {"type": "integer", "default": 0}},
                {
                    "name": "status",
                    "in": "query",
                    "schema": {"type": "string", "enum": ["paid", "open", "void"]},
                },
            ],
            "responses": {
                "200": {
                    "description": "Invoice list",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/CollectionResponse"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/billing/invoices/{invoice_id}": {
        "get": {
            "summary": "Get invoice details",
            "description": "Get full details for a specific invoice including download links.",
            "operationId": "getInvoice",
            "tags": ["Billing"],
            "parameters": [
                {
                    "name": "invoice_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                },
            ],
            "responses": {
                "200": {
                    "description": "Invoice details",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Invoice"},
                        },
                    },
                },
                "404": {
                    "description": "Invoice not found",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/billing/payment-methods": {
        "get": {
            "summary": "List payment methods",
            "description": "List saved payment methods for the authenticated user.",
            "operationId": "listPaymentMethods",
            "tags": ["Billing"],
            "responses": {
                "200": {
                    "description": "Payment methods",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/PaymentMethod"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "/api/v1/billing/payment-methods/setup": {
        "post": {
            "summary": "Create setup intent",
            "description": "Create a Stripe SetupIntent to add a new payment method. Returns a client_secret for Stripe.js.",
            "operationId": "createSetupIntent",
            "tags": ["Billing"],
            "responses": {
                "200": {
                    "description": "Setup intent created",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "client_secret": {
                                        "type": "string",
                                        "description": "Stripe SetupIntent client secret for frontend use",
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "/api/v1/billing/usage": {
        "get": {
            "summary": "Get current usage",
            "description": "Get detailed usage metrics for the current billing period.",
            "operationId": "getUsage",
            "tags": ["Billing"],
            "responses": {
                "200": {
                    "description": "Usage metrics",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/UsageMetrics"},
                        },
                    },
                },
            },
        },
    },
    "/api/v1/billing/webhooks/stripe": {
        "post": {
            "summary": "Stripe webhook handler",
            "description": (
                "Receives Stripe webhook events. Verifies the Stripe-Signature header using "
                "the webhook signing secret. Handles: checkout.session.completed, "
                "invoice.payment_succeeded, invoice.payment_failed, "
                "customer.subscription.updated, customer.subscription.deleted."
            ),
            "operationId": "handleStripeWebhook",
            "tags": ["Webhooks - Stripe"],
            "security": [],
            "parameters": [
                {
                    "name": "Stripe-Signature",
                    "in": "header",
                    "required": True,
                    "schema": {"type": "string"},
                    "description": "Stripe webhook signature for event verification",
                },
            ],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/StripeWebhookEvent"},
                    },
                },
            },
            "responses": {
                "200": {"description": "Event processed"},
                "400": {
                    "description": "Invalid signature or payload",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
    },
}
