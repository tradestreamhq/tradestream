# Viral Trading Platform - Implementation Plan

## Overview

Implementing the viral trading signal platform as specified in `specs/viral-platform/SPEC.md`.

## Phase 0: Database Migrations (Foundation)

Reference: `specs/viral-platform/database-migrations/SPEC.md`

- [x] Create V6\_\_add_users.sql - users, email_verification_tokens, password_reset_tokens, refresh_tokens tables
- [x] Create V7\_\_add_user_settings.sql - user_settings, user_watchlists, saved_views tables
- [x] Create V8\_\_add_notifications.sql - notification_channels, notification_preferences, notification_history tables

## Phase 1: Backend Services

Reference: `specs/viral-platform/gateway-api/SPEC.md`, `specs/viral-platform/auth-service/SPEC.md`

- [x] Create services/gateway/ directory structure with main.py, config.py
- [x] Implement auth router - /auth/register, /auth/login, /auth/logout endpoints
- [x] Implement OAuth router - /auth/oauth/{provider} and callback endpoints
- [x] Implement email service with Resend integration
- [x] Implement signal SSE endpoint - /api/signals/stream
- [x] Implement user settings router - /api/user/settings, /api/user/watchlist
- [x] Create Dockerfile for gateway-api
- [x] Create requirements.txt for gateway-api

## Phase 2: Helm Deployment

Reference: `specs/viral-platform/helm-deployment/SPEC.md`

- [x] Create charts/tradestream/templates/gateway-api.yaml
- [x] Create charts/tradestream/templates/auth-secrets.yaml
- [x] Create charts/tradestream/templates/oauth-secrets.yaml
- [x] Update charts/tradestream/values.yaml with gatewayApi configuration

## Phase 3: Frontend Foundation

Reference: `specs/viral-platform/agent-dashboard/SPEC.md`

- [x] Create ui/agent-dashboard/ with Vite + React + TypeScript scaffold
- [x] Configure Tailwind CSS and shadcn/ui
- [x] Create useAuth hook for authentication state
- [x] Create auth API client
- [x] Create Landing page component
- [x] Create Login page with OAuth buttons
- [x] Create Register page with form validation
- [x] Create ProtectedRoute component
- [x] Create Dashboard layout with header and sidebar

## Progress Tracking

| Phase             | Status   | Tasks Done | Tasks Total |
| ----------------- | -------- | ---------- | ----------- |
| Phase 0: Database | Complete | 3          | 3           |
| Phase 1: Backend  | Complete | 8          | 8           |
| Phase 2: Helm     | Complete | 4          | 4           |
| Phase 3: Frontend | Complete | 9          | 9           |

Last Updated: 2026-02-05
