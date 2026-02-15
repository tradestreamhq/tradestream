# Helm Deployment Specification

## Goal

Deploy the viral trading platform services to Kubernetes using Helm templates that integrate with the existing TradeStream chart infrastructure.

## Target Behavior

New services are deployed as part of the existing `tradestream` Helm chart, following established patterns for Deployments, Services, ConfigMaps, and Secrets.

## New Services

| Service | Type | Port | Description |
|---------|------|------|-------------|
| gateway-api | Deployment | 8000 | Unified FastAPI backend |
| agent-dashboard | Deployment | 80 | React frontend |
| notification-worker | CronJob | - | Push/Telegram notifications |

## File Structure

```
charts/tradestream/
├── Chart.yaml                    # Updated with new services
├── values.yaml                   # Updated with new configuration
└── templates/
    ├── _helpers.tpl              # Existing helpers
    ├── gateway-api.yaml          # NEW: Gateway API deployment
    ├── agent-dashboard.yaml      # NEW: Frontend deployment
    ├── notification-worker.yaml  # NEW: Notification CronJob
    ├── auth-secrets.yaml         # NEW: Auth secrets
    ├── oauth-secrets.yaml        # NEW: OAuth secrets
    └── ... (existing templates)
```

## Gateway API Template

### gateway-api.yaml

```yaml
{{- if .Values.gatewayApi.enabled }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "tradestream.fullname" . }}-gateway-api
  labels:
    {{- include "tradestream.labels" . | nindent 4 }}
    app.kubernetes.io/component: gateway-api
spec:
  replicas: {{ .Values.gatewayApi.replicaCount }}
  selector:
    matchLabels:
      {{- include "tradestream.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: gateway-api
  template:
    metadata:
      labels:
        {{- include "tradestream.selectorLabels" . | nindent 8 }}
        app.kubernetes.io/component: gateway-api
      annotations:
        checksum/auth-secrets: {{ include (print $.Template.BasePath "/auth-secrets.yaml") . | sha256sum }}
        checksum/oauth-secrets: {{ include (print $.Template.BasePath "/oauth-secrets.yaml") . | sha256sum }}
    spec:
      serviceAccountName: {{ include "tradestream.serviceAccountName" . }}
      containers:
        - name: gateway-api
          image: "{{ .Values.gatewayApi.image.repository }}:{{ .Values.gatewayApi.image.tag }}"
          imagePullPolicy: {{ .Values.gatewayApi.image.pullPolicy }}
          ports:
            - name: http
              containerPort: 8000
              protocol: TCP
          env:
            # Database
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: {{ include "tradestream.fullname" . }}-postgresql
                  key: postgres-url
            - name: DATABASE_POOL_SIZE
              value: "{{ .Values.gatewayApi.database.poolSize }}"

            # Redis
            - name: REDIS_URL
              value: "redis://{{ include "tradestream.fullname" . }}-redis-master:6379"

            # JWT
            - name: JWT_SECRET
              valueFrom:
                secretKeyRef:
                  name: {{ include "tradestream.fullname" . }}-auth-secrets
                  key: jwt-secret
            - name: JWT_ALGORITHM
              value: "HS256"

            # OAuth - Google
            - name: GOOGLE_CLIENT_ID
              valueFrom:
                secretKeyRef:
                  name: {{ include "tradestream.fullname" . }}-oauth-secrets
                  key: google-client-id
            - name: GOOGLE_CLIENT_SECRET
              valueFrom:
                secretKeyRef:
                  name: {{ include "tradestream.fullname" . }}-oauth-secrets
                  key: google-client-secret

            # OAuth - GitHub
            - name: GITHUB_CLIENT_ID
              valueFrom:
                secretKeyRef:
                  name: {{ include "tradestream.fullname" . }}-oauth-secrets
                  key: github-client-id
            - name: GITHUB_CLIENT_SECRET
              valueFrom:
                secretKeyRef:
                  name: {{ include "tradestream.fullname" . }}-oauth-secrets
                  key: github-client-secret

            # Email (Resend)
            - name: RESEND_API_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ include "tradestream.fullname" . }}-auth-secrets
                  key: resend-api-key

            # URLs
            - name: API_URL
              value: "{{ .Values.gatewayApi.urls.api }}"
            - name: FRONTEND_URL
              value: "{{ .Values.gatewayApi.urls.frontend }}"

            # CORS
            - name: CORS_ORIGINS
              value: "{{ .Values.gatewayApi.cors.origins | join "," }}"

            # Rate Limiting
            - name: RATE_LIMIT_PER_MINUTE
              value: "{{ .Values.gatewayApi.rateLimit.perMinute }}"

          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3

          readinessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 3

          resources:
            {{- toYaml .Values.gatewayApi.resources | nindent 12 }}

      {{- with .Values.gatewayApi.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}

      {{- with .Values.gatewayApi.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}

      {{- with .Values.gatewayApi.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}

---
apiVersion: v1
kind: Service
metadata:
  name: {{ include "tradestream.fullname" . }}-gateway-api
  labels:
    {{- include "tradestream.labels" . | nindent 4 }}
    app.kubernetes.io/component: gateway-api
spec:
  type: {{ .Values.gatewayApi.service.type }}
  ports:
    - port: {{ .Values.gatewayApi.service.port }}
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{- include "tradestream.selectorLabels" . | nindent 4 }}
    app.kubernetes.io/component: gateway-api

{{- if .Values.gatewayApi.ingress.enabled }}
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "tradestream.fullname" . }}-gateway-api
  labels:
    {{- include "tradestream.labels" . | nindent 4 }}
    app.kubernetes.io/component: gateway-api
  {{- with .Values.gatewayApi.ingress.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  {{- if .Values.gatewayApi.ingress.className }}
  ingressClassName: {{ .Values.gatewayApi.ingress.className }}
  {{- end }}
  {{- if .Values.gatewayApi.ingress.tls }}
  tls:
    {{- range .Values.gatewayApi.ingress.tls }}
    - hosts:
        {{- range .hosts }}
        - {{ . | quote }}
        {{- end }}
      secretName: {{ .secretName }}
    {{- end }}
  {{- end }}
  rules:
    {{- range .Values.gatewayApi.ingress.hosts }}
    - host: {{ .host | quote }}
      http:
        paths:
          {{- range .paths }}
          - path: {{ .path }}
            pathType: {{ .pathType }}
            backend:
              service:
                name: {{ include "tradestream.fullname" $ }}-gateway-api
                port:
                  number: {{ $.Values.gatewayApi.service.port }}
          {{- end }}
    {{- end }}
{{- end }}
{{- end }}
```

## Agent Dashboard Template

### agent-dashboard.yaml

```yaml
{{- if .Values.agentDashboard.enabled }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "tradestream.fullname" . }}-agent-dashboard
  labels:
    {{- include "tradestream.labels" . | nindent 4 }}
    app.kubernetes.io/component: agent-dashboard
spec:
  replicas: {{ .Values.agentDashboard.replicaCount }}
  selector:
    matchLabels:
      {{- include "tradestream.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: agent-dashboard
  template:
    metadata:
      labels:
        {{- include "tradestream.selectorLabels" . | nindent 8 }}
        app.kubernetes.io/component: agent-dashboard
    spec:
      serviceAccountName: {{ include "tradestream.serviceAccountName" . }}
      containers:
        - name: agent-dashboard
          image: "{{ .Values.agentDashboard.image.repository }}:{{ .Values.agentDashboard.image.tag }}"
          imagePullPolicy: {{ .Values.agentDashboard.image.pullPolicy }}
          ports:
            - name: http
              containerPort: 80
              protocol: TCP

          livenessProbe:
            httpGet:
              path: /
              port: http
            initialDelaySeconds: 5
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3

          readinessProbe:
            httpGet:
              path: /
              port: http
            initialDelaySeconds: 3
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 3

          resources:
            {{- toYaml .Values.agentDashboard.resources | nindent 12 }}

      {{- with .Values.agentDashboard.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}

      {{- with .Values.agentDashboard.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}

      {{- with .Values.agentDashboard.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}

---
apiVersion: v1
kind: Service
metadata:
  name: {{ include "tradestream.fullname" . }}-agent-dashboard
  labels:
    {{- include "tradestream.labels" . | nindent 4 }}
    app.kubernetes.io/component: agent-dashboard
spec:
  type: {{ .Values.agentDashboard.service.type }}
  ports:
    - port: {{ .Values.agentDashboard.service.port }}
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{- include "tradestream.selectorLabels" . | nindent 4 }}
    app.kubernetes.io/component: agent-dashboard

{{- if .Values.agentDashboard.ingress.enabled }}
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "tradestream.fullname" . }}-agent-dashboard
  labels:
    {{- include "tradestream.labels" . | nindent 4 }}
    app.kubernetes.io/component: agent-dashboard
  {{- with .Values.agentDashboard.ingress.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  {{- if .Values.agentDashboard.ingress.className }}
  ingressClassName: {{ .Values.agentDashboard.ingress.className }}
  {{- end }}
  {{- if .Values.agentDashboard.ingress.tls }}
  tls:
    {{- range .Values.agentDashboard.ingress.tls }}
    - hosts:
        {{- range .hosts }}
        - {{ . | quote }}
        {{- end }}
      secretName: {{ .secretName }}
    {{- end }}
  {{- end }}
  rules:
    {{- range .Values.agentDashboard.ingress.hosts }}
    - host: {{ .host | quote }}
      http:
        paths:
          {{- range .paths }}
          - path: {{ .path }}
            pathType: {{ .pathType }}
            backend:
              service:
                name: {{ include "tradestream.fullname" $ }}-agent-dashboard
                port:
                  number: {{ $.Values.agentDashboard.service.port }}
          {{- end }}
    {{- end }}
{{- end }}
{{- end }}
```

## Notification Worker Template

### notification-worker.yaml

```yaml
{{- if .Values.notificationWorker.enabled }}
apiVersion: batch/v1
kind: CronJob
metadata:
  name: {{ include "tradestream.fullname" . }}-notification-worker
  labels:
    {{- include "tradestream.labels" . | nindent 4 }}
    app.kubernetes.io/component: notification-worker
spec:
  schedule: "{{ .Values.notificationWorker.schedule }}"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      template:
        metadata:
          labels:
            {{- include "tradestream.selectorLabels" . | nindent 12 }}
            app.kubernetes.io/component: notification-worker
        spec:
          serviceAccountName: {{ include "tradestream.serviceAccountName" . }}
          restartPolicy: OnFailure
          containers:
            - name: notification-worker
              image: "{{ .Values.notificationWorker.image.repository }}:{{ .Values.notificationWorker.image.tag }}"
              imagePullPolicy: {{ .Values.notificationWorker.image.pullPolicy }}
              env:
                # Database
                - name: DATABASE_URL
                  valueFrom:
                    secretKeyRef:
                      name: {{ include "tradestream.fullname" . }}-postgresql
                      key: postgres-url

                # Redis
                - name: REDIS_URL
                  value: "redis://{{ include "tradestream.fullname" . }}-redis-master:6379"

                # Push notifications
                - name: VAPID_PRIVATE_KEY
                  valueFrom:
                    secretKeyRef:
                      name: {{ include "tradestream.fullname" . }}-notification-secrets
                      key: vapid-private-key
                - name: VAPID_PUBLIC_KEY
                  valueFrom:
                    secretKeyRef:
                      name: {{ include "tradestream.fullname" . }}-notification-secrets
                      key: vapid-public-key

                # Telegram
                - name: TELEGRAM_BOT_TOKEN
                  valueFrom:
                    secretKeyRef:
                      name: {{ include "tradestream.fullname" . }}-notification-secrets
                      key: telegram-bot-token
                      optional: true

                # Email (Resend)
                - name: RESEND_API_KEY
                  valueFrom:
                    secretKeyRef:
                      name: {{ include "tradestream.fullname" . }}-auth-secrets
                      key: resend-api-key

              resources:
                {{- toYaml .Values.notificationWorker.resources | nindent 16 }}

          {{- with .Values.notificationWorker.nodeSelector }}
          nodeSelector:
            {{- toYaml . | nindent 12 }}
          {{- end }}

          {{- with .Values.notificationWorker.tolerations }}
          tolerations:
            {{- toYaml . | nindent 12 }}
          {{- end }}
{{- end }}
```

## Secrets Templates

### auth-secrets.yaml

```yaml
{{- if .Values.authSecrets.create }}
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "tradestream.fullname" . }}-auth-secrets
  labels:
    {{- include "tradestream.labels" . | nindent 4 }}
type: Opaque
data:
  {{- if .Values.authSecrets.jwtSecret }}
  jwt-secret: {{ .Values.authSecrets.jwtSecret | b64enc | quote }}
  {{- else }}
  jwt-secret: {{ randAlphaNum 64 | b64enc | quote }}
  {{- end }}
  resend-api-key: {{ .Values.authSecrets.resendApiKey | b64enc | quote }}
{{- end }}
```

### oauth-secrets.yaml

```yaml
{{- if .Values.oauthSecrets.create }}
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "tradestream.fullname" . }}-oauth-secrets
  labels:
    {{- include "tradestream.labels" . | nindent 4 }}
type: Opaque
data:
  google-client-id: {{ .Values.oauthSecrets.google.clientId | b64enc | quote }}
  google-client-secret: {{ .Values.oauthSecrets.google.clientSecret | b64enc | quote }}
  github-client-id: {{ .Values.oauthSecrets.github.clientId | b64enc | quote }}
  github-client-secret: {{ .Values.oauthSecrets.github.clientSecret | b64enc | quote }}
{{- end }}
```

### notification-secrets.yaml

```yaml
{{- if .Values.notificationSecrets.create }}
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "tradestream.fullname" . }}-notification-secrets
  labels:
    {{- include "tradestream.labels" . | nindent 4 }}
type: Opaque
data:
  vapid-private-key: {{ .Values.notificationSecrets.vapidPrivateKey | b64enc | quote }}
  vapid-public-key: {{ .Values.notificationSecrets.vapidPublicKey | b64enc | quote }}
  {{- if .Values.notificationSecrets.telegramBotToken }}
  telegram-bot-token: {{ .Values.notificationSecrets.telegramBotToken | b64enc | quote }}
  {{- end }}
{{- end }}
```

## Values.yaml Additions

```yaml
# Gateway API Configuration
gatewayApi:
  enabled: true
  replicaCount: 2

  image:
    repository: tradestreamhq/gateway-api
    tag: v1.0.0
    pullPolicy: IfNotPresent

  database:
    poolSize: 10

  urls:
    api: https://api.tradestream.io
    frontend: https://tradestream.io

  cors:
    origins:
      - https://tradestream.io
      - https://www.tradestream.io
      - http://localhost:3000

  rateLimit:
    perMinute: 60

  service:
    type: ClusterIP
    port: 8000

  ingress:
    enabled: true
    className: nginx
    annotations:
      cert-manager.io/cluster-issuer: letsencrypt-prod
      nginx.ingress.kubernetes.io/proxy-body-size: 10m
      nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
      nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
    hosts:
      - host: api.tradestream.io
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: gateway-api-tls
        hosts:
          - api.tradestream.io

  resources:
    requests:
      cpu: 200m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 512Mi

  nodeSelector: {}
  tolerations: []
  affinity: {}

# Agent Dashboard Configuration
agentDashboard:
  enabled: true
  replicaCount: 2

  image:
    repository: tradestreamhq/agent-dashboard
    tag: v1.0.0
    pullPolicy: IfNotPresent

  service:
    type: ClusterIP
    port: 80

  ingress:
    enabled: true
    className: nginx
    annotations:
      cert-manager.io/cluster-issuer: letsencrypt-prod
      nginx.ingress.kubernetes.io/proxy-body-size: 10m
    hosts:
      - host: tradestream.io
        paths:
          - path: /
            pathType: Prefix
      - host: www.tradestream.io
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: agent-dashboard-tls
        hosts:
          - tradestream.io
          - www.tradestream.io

  resources:
    requests:
      cpu: 50m
      memory: 64Mi
    limits:
      cpu: 100m
      memory: 128Mi

  nodeSelector: {}
  tolerations: []
  affinity: {}

# Notification Worker Configuration
notificationWorker:
  enabled: true
  schedule: "*/5 * * * *"  # Every 5 minutes

  image:
    repository: tradestreamhq/notification-worker
    tag: v1.0.0
    pullPolicy: IfNotPresent

  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 200m
      memory: 256Mi

  nodeSelector: {}
  tolerations: []

# Auth Secrets
authSecrets:
  create: true
  # jwtSecret: ""  # Leave empty to auto-generate
  resendApiKey: ""  # Required: Set via --set or values file

# OAuth Secrets
oauthSecrets:
  create: true
  google:
    clientId: ""
    clientSecret: ""
  github:
    clientId: ""
    clientSecret: ""

# Notification Secrets
notificationSecrets:
  create: true
  vapidPrivateKey: ""
  vapidPublicKey: ""
  telegramBotToken: ""  # Optional
```

## Deployment Commands

### Create Secrets (Manual)

For sensitive values, create secrets outside of Helm:

```bash
# Auth secrets
kubectl create secret generic tradestream-auth-secrets \
  --namespace tradestream \
  --from-literal=jwt-secret=$(openssl rand -hex 32) \
  --from-literal=resend-api-key=$RESEND_API_KEY

# OAuth secrets
kubectl create secret generic tradestream-oauth-secrets \
  --namespace tradestream \
  --from-literal=google-client-id=$GOOGLE_CLIENT_ID \
  --from-literal=google-client-secret=$GOOGLE_CLIENT_SECRET \
  --from-literal=github-client-id=$GITHUB_CLIENT_ID \
  --from-literal=github-client-secret=$GITHUB_CLIENT_SECRET

# Notification secrets (generate VAPID keys with: npx web-push generate-vapid-keys)
kubectl create secret generic tradestream-notification-secrets \
  --namespace tradestream \
  --from-literal=vapid-private-key=$VAPID_PRIVATE_KEY \
  --from-literal=vapid-public-key=$VAPID_PUBLIC_KEY \
  --from-literal=telegram-bot-token=$TELEGRAM_BOT_TOKEN
```

Then set `authSecrets.create=false`, `oauthSecrets.create=false`, `notificationSecrets.create=false` in values.

### Deploy with Helm

```bash
# Install/upgrade with new services
helm upgrade --install tradestream charts/tradestream \
  --namespace tradestream \
  --create-namespace \
  --set gatewayApi.enabled=true \
  --set agentDashboard.enabled=true \
  --set notificationWorker.enabled=true \
  --set authSecrets.create=false \
  --set oauthSecrets.create=false \
  --set notificationSecrets.create=false \
  -f values-production.yaml
```

### Verify Deployment

```bash
# Check pods
kubectl get pods -n tradestream -l app.kubernetes.io/component=gateway-api
kubectl get pods -n tradestream -l app.kubernetes.io/component=agent-dashboard

# Check services
kubectl get svc -n tradestream

# Check ingress
kubectl get ingress -n tradestream

# Check logs
kubectl logs -n tradestream -l app.kubernetes.io/component=gateway-api -f
```

## Horizontal Pod Autoscaler (Optional)

### gateway-api-hpa.yaml

```yaml
{{- if .Values.gatewayApi.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "tradestream.fullname" . }}-gateway-api
  labels:
    {{- include "tradestream.labels" . | nindent 4 }}
    app.kubernetes.io/component: gateway-api
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "tradestream.fullname" . }}-gateway-api
  minReplicas: {{ .Values.gatewayApi.autoscaling.minReplicas }}
  maxReplicas: {{ .Values.gatewayApi.autoscaling.maxReplicas }}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ .Values.gatewayApi.autoscaling.targetCPUUtilization }}
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: {{ .Values.gatewayApi.autoscaling.targetMemoryUtilization }}
{{- end }}
```

Add to values.yaml:

```yaml
gatewayApi:
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilization: 70
    targetMemoryUtilization: 80
```

## Network Policy (Optional)

### gateway-api-network-policy.yaml

```yaml
{{- if .Values.gatewayApi.networkPolicy.enabled }}
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "tradestream.fullname" . }}-gateway-api
  labels:
    {{- include "tradestream.labels" . | nindent 4 }}
    app.kubernetes.io/component: gateway-api
spec:
  podSelector:
    matchLabels:
      {{- include "tradestream.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: gateway-api
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: agent-dashboard
      ports:
        - protocol: TCP
          port: 8000
  egress:
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: postgresql
      ports:
        - protocol: TCP
          port: 5432
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: redis
      ports:
        - protocol: TCP
          port: 6379
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
{{- end }}
```

## Constraints

- All templates must pass `helm lint`
- Templates must support dry-run without errors
- Secrets should be created separately for production
- Ingress requires cert-manager for TLS
- Resources must be configured for production load
- Health probes must be configured

## Acceptance Criteria

- [ ] `helm lint charts/tradestream` passes
- [ ] `helm template tradestream charts/tradestream` renders all templates
- [ ] Gateway API deployment creates pods successfully
- [ ] Gateway API service routes traffic correctly
- [ ] Gateway API ingress exposes API externally
- [ ] Agent Dashboard deployment creates pods successfully
- [ ] Agent Dashboard ingress serves frontend
- [ ] Notification Worker CronJob runs on schedule
- [ ] Secrets are properly mounted in containers
- [ ] Health checks pass on all services
- [ ] TLS certificates provisioned via cert-manager
- [ ] HPA scales gateway-api under load
- [ ] Rolling updates work without downtime

## Notes

### Database Migration

Ensure database migrations run before deploying gateway-api:

```bash
# Migrations run automatically via existing database-migration job
# Check job status before deploying
kubectl get jobs -n tradestream -l app.kubernetes.io/component=database-migration
```

### Image Building

Build and push images before deployment:

```bash
# Gateway API
cd services/gateway
docker build -t tradestreamhq/gateway-api:v1.0.0 .
docker push tradestreamhq/gateway-api:v1.0.0

# Agent Dashboard
cd ui/agent-dashboard
docker build -t tradestreamhq/agent-dashboard:v1.0.0 .
docker push tradestreamhq/agent-dashboard:v1.0.0

# Notification Worker
cd services/notification_worker
docker build -t tradestreamhq/notification-worker:v1.0.0 .
docker push tradestreamhq/notification-worker:v1.0.0
```

### Monitoring

Add Prometheus annotations for scraping:

```yaml
template:
  metadata:
    annotations:
      prometheus.io/scrape: "true"
      prometheus.io/port: "8000"
      prometheus.io/path: "/metrics"
```
