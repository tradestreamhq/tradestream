# ArgoCD Strategy Monitor Services Fix

## Issue
The strategy monitor API and UI services are not being deployed on the cluster, even though they are enabled by default in the Helm chart.

## Root Cause
The ArgoCD application is missing the Helm parameters for the strategy monitor services. While the ArgoCD Image Updater is configured to watch these images, the services are not being deployed because their Helm parameters are not set.

## Current Status
- ✅ ArgoCD Image Updater is configured to watch:
  - `strategy-monitor-api=tradestreamhq/strategy-monitor-api`
  - `strategy-monitor-ui=tradestreamhq/strategy-monitor-ui`
- ✅ Helm chart has strategy monitor services enabled by default
- ❌ ArgoCD application is missing Helm parameters for strategy monitor services

## Required Fix
Add the following Helm parameters to the ArgoCD application `tradestream-dev`:

```yaml
spec:
  source:
    helm:
      parameters:
      # ... existing parameters ...
      - forceString: true
        name: strategyMonitorApi.image.repository
        value: tradestreamhq/strategy-monitor-api
      - forceString: true
        name: strategyMonitorApi.image.tag
        value: v1.0.11
      - forceString: true
        name: strategyMonitorUi.image.repository
        value: tradestreamhq/strategy-monitor-ui
      - forceString: true
        name: strategyMonitorUi.image.tag
        value: v1.0.11
```

## Expected Result
After adding these parameters:
1. The strategy monitor API service will be deployed as `tradestream-dev-strategy-monitor-api`
2. The strategy monitor UI service will be deployed as `tradestream-dev-strategy-monitor-ui`
3. Both services will be automatically updated by ArgoCD Image Updater when new versions are available
4. The UI will be accessible at the cluster service endpoint

## Verification
After the fix is applied, verify the services are deployed:
```bash
kubectl get deployments -n tradestream-dev | grep strategy-monitor
kubectl get services -n tradestream-dev | grep strategy-monitor
```

## Current Workaround
The strategy visualization UI is currently working via a hybrid approach:
- Local API server (port 8080) connecting to cluster PostgreSQL
- Local UI server (port 3001) serving static files
- This provides full functionality while the cluster services are being configured 