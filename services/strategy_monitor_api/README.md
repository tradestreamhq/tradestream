# Strategy Monitor API

The Strategy Monitor API provides a RESTful interface for monitoring, managing, and analyzing trading strategies in the TradeStream platform. It serves as the primary API for the web-based strategy monitoring interface.

## Production System Overview

The Strategy Monitor API is currently in development:

- **Technology**: FastAPI with JWT authentication
- **Features**: Strategy data endpoints, real-time monitoring
- **Status**: 🔄 **IN DEVELOPMENT** - Codebase ready, pending deployment
- **Integration**: PostgreSQL strategy data, InfluxDB market data, Kafka real-time events
- **Documentation**: Auto-generated OpenAPI/Swagger documentation

## Overview

The Strategy Monitor API provides:

- **Strategy Management**: CRUD operations for trading strategies
- **Performance Analytics**: Real-time and historical performance metrics
- **Strategy Monitoring**: Live monitoring of active strategies
- **Alert Management**: Strategy performance alerts and notifications
- **Configuration Management**: Strategy parameter configuration
- **Reporting**: Performance reports and analytics

## Architecture

### API Structure

```
Strategy Monitor API
├── /api/v1/strategies          # Strategy management endpoints
├── /api/v1/performance         # Performance analytics endpoints
├── /api/v1/alerts              # Alert management endpoints
├── /api/v1/config              # Configuration endpoints
└── /api/v1/reports             # Reporting endpoints
```

### Technology Stack

- **Framework**: FastAPI (Python 3.13)
- **Database**: PostgreSQL for strategy storage
- **Cache**: Redis for performance caching
- **Authentication**: JWT-based authentication
- **Documentation**: Auto-generated OpenAPI/Swagger docs

## API Endpoints

### Strategy Management

#### Get All Strategies

```http
GET /api/v1/strategies
```

**Response:**

```json
{
  "strategies": [
    {
      "id": "strategy_123",
      "type": "MACD_CROSSOVER",
      "symbol": "BTC/USD",
      "timeframe": "1h",
      "parameters": {
        "short_period": 12,
        "long_period": 26,
        "signal_period": 9
      },
      "status": "active",
      "created_at": "2023-01-01T00:00:00Z",
      "updated_at": "2023-01-01T00:00:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "per_page": 20
}
```

#### Get Strategy by ID

```http
GET /api/v1/strategies/{strategy_id}
```

#### Create Strategy

```http
POST /api/v1/strategies
Content-Type: application/json

{
  "type": "MACD_CROSSOVER",
  "symbol": "BTC/USD",
  "timeframe": "1h",
  "parameters": {
    "short_period": 12,
    "long_period": 26,
    "signal_period": 9
  }
}
```

#### Update Strategy

```http
PUT /api/v1/strategies/{strategy_id}
Content-Type: application/json

{
  "parameters": {
    "short_period": 14,
    "long_period": 28,
    "signal_period": 9
  },
  "status": "paused"
}
```

#### Delete Strategy

```http
DELETE /api/v1/strategies/{strategy_id}
```

### Performance Analytics

#### Get Strategy Performance

```http
GET /api/v1/strategies/{strategy_id}/performance
```

**Response:**

```json
{
  "strategy_id": "strategy_123",
  "performance": {
    "total_return": 0.15,
    "sharpe_ratio": 1.2,
    "max_drawdown": -0.05,
    "win_rate": 0.65,
    "profit_factor": 1.8,
    "total_trades": 150,
    "avg_trade_duration": 2.5,
    "current_equity": 11500.0,
    "peak_equity": 12000.0
  },
  "period": {
    "start": "2023-01-01T00:00:00Z",
    "end": "2023-12-31T23:59:59Z"
  }
}
```

#### Get Performance History

```http
GET /api/v1/strategies/{strategy_id}/performance/history
?start_date=2023-01-01&end_date=2023-12-31&granularity=daily
```

#### Get Real-time Performance

```http
GET /api/v1/strategies/{strategy_id}/performance/realtime
```

### Alert Management

#### Get Alerts

```http
GET /api/v1/alerts
```

**Response:**

```json
{
  "alerts": [
    {
      "id": "alert_123",
      "strategy_id": "strategy_123",
      "type": "drawdown",
      "severity": "warning",
      "message": "Strategy drawdown exceeded 5%",
      "value": -0.06,
      "threshold": -0.05,
      "created_at": "2023-01-01T10:30:00Z",
      "status": "active"
    }
  ]
}
```

#### Create Alert

```http
POST /api/v1/alerts
Content-Type: application/json

{
  "strategy_id": "strategy_123",
  "type": "drawdown",
  "threshold": -0.05,
  "severity": "warning",
  "enabled": true
}
```

#### Update Alert

```http
PUT /api/v1/alerts/{alert_id}
Content-Type: application/json

{
  "threshold": -0.03,
  "enabled": false
}
```

### Configuration Management

#### Get Strategy Configuration

```http
GET /api/v1/strategies/{strategy_id}/config
```

#### Update Strategy Configuration

```http
PUT /api/v1/strategies/{strategy_id}/config
Content-Type: application/json

{
  "risk_management": {
    "max_position_size": 0.1,
    "stop_loss": 0.02,
    "take_profit": 0.04
  },
  "execution": {
    "slippage_tolerance": 0.001,
    "max_retries": 3
  }
}
```

### Reporting

#### Get Performance Report

```http
GET /api/v1/reports/performance
?start_date=2023-01-01&end_date=2023-12-31&group_by=month
```

#### Get Strategy Comparison

```http
GET /api/v1/reports/comparison
?strategy_ids=strategy_123,strategy_456&period=1y
```

## Authentication

### JWT Authentication

The API uses JWT tokens for authentication:

```http
Authorization: Bearer <jwt_token>
```

### Token Endpoints

#### Login

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "password123"
}
```

**Response:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

#### Refresh Token

```http
POST /api/v1/auth/refresh
Authorization: Bearer <refresh_token>
```

## Error Handling

### Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid strategy parameters",
    "details": {
      "field": "short_period",
      "value": -1,
      "constraint": "must be positive"
    }
  },
  "timestamp": "2023-01-01T10:30:00Z",
  "request_id": "req_123"
}
```

### Common Error Codes

- `VALIDATION_ERROR`: Invalid request parameters
- `NOT_FOUND`: Resource not found
- `UNAUTHORIZED`: Authentication required
- `FORBIDDEN`: Insufficient permissions
- `INTERNAL_ERROR`: Server error
- `RATE_LIMIT_EXCEEDED`: Too many requests

## Rate Limiting

### Rate Limit Headers

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

### Rate Limit Rules

- **Authenticated users**: 1000 requests per hour
- **Unauthenticated users**: 100 requests per hour
- **Admin users**: 5000 requests per hour

## WebSocket Support

### Real-time Updates

```javascript
// Connect to WebSocket
const ws = new WebSocket("ws://localhost:8080/ws/strategies");

// Listen for real-time updates
ws.onmessage = function (event) {
  const data = JSON.parse(event.data);

  if (data.type === "performance_update") {
    updatePerformanceChart(data.strategy_id, data.performance);
  } else if (data.type === "alert") {
    showAlert(data.alert);
  }
};
```

### WebSocket Events

- `performance_update`: Real-time performance metrics
- `alert`: New alert notifications
- `strategy_status_change`: Strategy status updates
- `trade_execution`: New trade executions

## Configuration

### Environment Variables

```bash
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/tradestream
REDIS_URL=redis://localhost:6379

# API Configuration
API_HOST=0.0.0.0
API_PORT=8080
API_WORKERS=4

# Authentication
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Rate Limiting
RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_WINDOW=3600

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Configuration File

```yaml
# config.yaml
api:
  host: 0.0.0.0
  port: 8080
  workers: 4
  cors_origins:
    - http://localhost:3000
    - https://tradestream.example.com

database:
  url: postgresql://user:password@localhost:5432/tradestream
  pool_size: 20
  max_overflow: 30

redis:
  url: redis://localhost:6379
  pool_size: 10

authentication:
  jwt_secret: your-secret-key
  jwt_algorithm: HS256
  jwt_expiration_hours: 24

rate_limiting:
  requests_per_hour: 1000
  window_seconds: 3600

logging:
  level: INFO
  format: json
  file: /var/log/strategy-monitor-api.log
```

## Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn main:app --reload --host 0.0.0.0 --port 8080

# Run tests
pytest tests/

# Run linting
black .
flake8 .
```

### Docker Development

```bash
# Build development image
docker build -t strategy-monitor-api:dev .

# Run development container
docker run -p 8080:8080 \
  -e DATABASE_URL=postgresql://user:password@host:5432/tradestream \
  -e REDIS_URL=redis://host:6379 \
  strategy-monitor-api:dev
```

## Testing

### Unit Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_strategies.py

# Run with coverage
pytest --cov=app --cov-report=html
```

### Integration Tests

```bash
# Run integration tests
pytest tests/integration/

# Run with real database
pytest tests/integration/ --database-url=postgresql://user:password@localhost:5432/test
```

### API Tests

```bash
# Run API tests
pytest tests/api/

# Test specific endpoint
pytest tests/api/test_strategies.py::test_get_strategies
```

## Deployment

### Docker Deployment

```dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: strategy-monitor-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: strategy-monitor-api
  template:
    metadata:
      labels:
        app: strategy-monitor-api
    spec:
      containers:
        - name: strategy-monitor-api
          image: tradestreamhq/strategy-monitor-api:latest
          ports:
            - containerPort: 8080
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: database-secret
                  key: url
            - name: REDIS_URL
              value: "redis://redis:6379"
            - name: JWT_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: jwt-secret
                  key: secret
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
```

## Monitoring

### Health Checks

```http
GET /health
```

**Response:**

```json
{
  "status": "healthy",
  "timestamp": "2023-01-01T10:30:00Z",
  "version": "1.0.0",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "external_apis": "healthy"
  }
}
```

### Metrics

The API exposes Prometheus metrics at `/metrics`:

```http
GET /metrics
```

### Key Metrics

- **Request Rate**: Requests per second
- **Response Time**: Average response time
- **Error Rate**: Percentage of failed requests
- **Active Connections**: Number of active WebSocket connections
- **Database Connections**: Active database connections

## Documentation

### Auto-generated Documentation

The API automatically generates OpenAPI/Swagger documentation:

- **Swagger UI**: `http://localhost:8080/docs`
- **ReDoc**: `http://localhost:8080/redoc`
- **OpenAPI JSON**: `http://localhost:8080/openapi.json`

### API Documentation

```python
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="Strategy Monitor API",
    description="API for monitoring and managing trading strategies",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Strategy Monitor API",
        version="1.0.0",
        description="API for monitoring and managing trading strategies",
        routes=app.routes,
    )

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

## Future Platform Vision

**Current Implementation**: The strategy monitoring API represents the first user-facing interface, providing real-time visualization of strategy discovery and performance metrics.

**Future Platform Vision**: Additional UI interfaces will be developed for portfolio management, risk monitoring, and trade execution, all served through a unified API gateway for a complete trading platform experience.

### Planned Platform Architecture

#### Web Applications Layer

```mermaid
graph TB
    subgraph "Web Applications"
        SMD[Strategy Monitor<br/>Dashboard]
        PMD[Portfolio Management<br/>Dashboard]
        TED[Trade Execution<br/>Dashboard]
        MOB[Mobile<br/>Applications]
    end

    AGW[API Gateway]

    SMD --> AGW
    PMD --> AGW
    TED --> AGW
    MOB --> AGW

    style SMD fill:#e1f5fe
    style PMD fill:#f3e5f5
    style TED fill:#fff3e0
    style MOB fill:#e8f5e8
    style AGW fill:#ffcdd2
```

#### API Gateway Services

```mermaid
graph TB
    subgraph "API Gateway Layer"
        AGW[API Gateway<br/>Kong/Ambassador]
        AUTH[Authentication Service<br/>OAuth2/JWT]
        RATE[Rate Limiting<br/>API Quotas]
        LOG[API Logging<br/>Audit & Analytics]
    end

    subgraph "Backend Services"
        SMA[Strategy Monitor API]
        PMA[Portfolio Management API]
        TEA[Trade Execution API]
        WS[WebSocket Services<br/>Real-time Updates]
    end

    AGW --> AUTH
    AGW --> RATE
    AGW --> LOG
    AGW --> SMA
    AGW --> PMA
    AGW --> TEA
    AGW --> WS

    style AGW fill:#ffcdd2
    style AUTH fill:#ffcdd2
    style RATE fill:#ffcdd2
    style LOG fill:#ffcdd2
```

#### Service Integration Flow

```mermaid
graph LR
    subgraph "Frontend"
        UI[Web Applications]
    end

    subgraph "Gateway"
        AGW[API Gateway]
    end

    subgraph "Services"
        SMA[Strategy Monitor API]
        PMA[Portfolio Management API]
        TEA[Trade Execution API]
    end

    subgraph "Real-time"
        WS[WebSocket Services]
        KAFKA[Kafka Topics]
    end

    UI --> AGW
    AGW --> SMA
    AGW --> PMA
    AGW --> TEA
    SMA --> WS
    PMA --> WS
    TEA --> WS
    WS --> KAFKA

    style UI fill:#e1f5fe
    style AGW fill:#ffcdd2
    style SMA fill:#f3e5f5
    style PMA fill:#f3e5f5
    style TEA fill:#f3e5f5
    style WS fill:#fff3e0
```

## Troubleshooting

### Common Issues

#### Database Connection Issues

```bash
# Check database connectivity
kubectl exec -it deployment/strategy-monitor-api -- nc -zv postgresql 5432

# Check database logs
kubectl logs deployment/postgresql
```

#### Redis Connection Issues

```bash
# Check Redis connectivity
kubectl exec -it deployment/strategy-monitor-api -- nc -zv redis 6379

# Check Redis logs
kubectl logs deployment/redis
```

#### High Memory Usage

```bash
# Check memory usage
kubectl top pod -l app=strategy-monitor-api

# Check memory limits
kubectl describe pod -l app=strategy-monitor-api
```

### Debug Commands

```bash
# Check API logs
kubectl logs deployment/strategy-monitor-api -f

# Port forward for local debugging
kubectl port-forward svc/strategy-monitor-api 8080:8080

# Check API health
curl http://localhost:8080/health

# Check API metrics
curl http://localhost:8080/metrics
```

## Contributing

When contributing to the Strategy Monitor API:

1. **Follow Patterns**: Use existing API patterns and conventions
2. **Add Tests**: Include comprehensive test coverage
3. **Update Documentation**: Keep API documentation current
4. **Performance**: Consider performance implications of changes
5. **Security**: Implement proper authentication and authorization

## License

This project is part of the TradeStream platform. See the root LICENSE file for details.
