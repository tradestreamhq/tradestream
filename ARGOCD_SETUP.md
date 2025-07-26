# ArgoCD Setup for TradeStream

This guide explains how to configure ArgoCD to automatically detect and use the latest image tags for your TradeStream services.

## Overview

Instead of manually updating `values.yaml` with new tags in your GitHub Actions workflow, ArgoCD can automatically:
1. Detect when new image tags are available
2. Update the deployment with the latest tags
3. Deploy the changes automatically

## Method 1: ArgoCD Built-in Image Substitution (Recommended)

This is the simplest approach using ArgoCD's built-in image substitution feature.

### 1. Create ArgoCD Application

Use the `argocd-app-simple.yaml` file:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: tradestream
  namespace: argocd
spec:
  source:
    repoURL: https://github.com/your-org/tradestream.git
    targetRevision: main
    path: charts/tradestream
    helm:
      # ArgoCD will automatically substitute these with the latest available tags
      image:
        - name: tradestreamhq/candle-ingestor
          value: tradestreamhq/candle-ingestor:latest
        - name: tradestreamhq/top-crypto-updater
          value: tradestreamhq/top-crypto-updater:latest
        # ... other services
```

### 2. Update Your Helm Templates

Update your Helm templates to use the substituted image tags. For example, in `candle-ingestor.yaml`:

```yaml
image: "{{ .Values.candleIngestor.image.repository }}:{{ .Values.candleIngestor.image.tag | default .Chart.AppVersion }}"
```

### 3. Deploy the Application

```bash
kubectl apply -f argocd-app-simple.yaml
```

## Method 2: ArgoCD Image Updater (Advanced)

For more control over image updates, use the ArgoCD Image Updater.

### 1. Install ArgoCD Image Updater

```bash
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj-labs/argocd-image-updater/stable/manifests/install.yaml
```

### 2. Create ArgoCD Application with Image Updater

Use the `argocd-app-with-image-updater.yaml` file which includes annotations for automatic image updates.

### 3. Configure Image Updater

The annotations in the application will:
- Monitor your Docker Hub repositories for new tags
- Match semantic versioning patterns (e.g., `v1.0.4-main`)
- Automatically update the application when new tags are found

## Method 3: GitOps with Tag Detection

This approach uses a custom script to detect the latest tag and update the Git repository.

### 1. Create a Tag Detection Script

```bash
#!/bin/bash
# detect-latest-tag.sh

# Get the latest tag from your release workflow
LATEST_TAG=$(git describe --tags --abbrev=0)

# Update values.yaml with the latest tag
yq eval-all '
  . as $item ireduce ({}; . * $item ) |
  .global.imageTag = "'$LATEST_TAG'" |
  .candleIngestor.image.tag = "'$LATEST_TAG'" |
  .topCryptoUpdaterCronjob.image.tag = "'$LATEST_TAG'" |
  .strategyDiscoveryRequestFactory.image.tag = "'$LATEST_TAG'" |
  .strategyDiscoveryPipeline.image.tag = "'$LATEST_TAG'" |
  .strategyConsumer.image.tag = "'$LATEST_TAG'" |
  .strategyMonitorApi.image.tag = "'$LATEST_TAG'" |
  .strategyMonitorUi.image.tag = "'$LATEST_TAG'"
' charts/tradestream/values.yaml > charts/tradestream/values.yaml.tmp
mv charts/tradestream/values.yaml.tmp charts/tradestream/values.yaml

# Commit and push changes
git add charts/tradestream/values.yaml
git commit -m "Update to latest tag: $LATEST_TAG"
git push
```

### 2. Integrate with Your Release Workflow

Add this to your `.github/workflows/release.yaml`:

```yaml
- name: Update ArgoCD Application
  run: |
    ./detect-latest-tag.sh
```

## How ArgoCD Detects Tags

### Built-in Image Substitution
- ArgoCD queries the container registry for the latest tag
- Uses the `:latest` tag or a specific pattern
- Automatically substitutes the image reference during deployment

### Image Updater
- Monitors container registries for new tags
- Uses regex patterns to match semantic versions
- Can write back to Git repository or update in-place

### Manual Detection
- Script queries Git tags or container registry
- Updates values.yaml with the latest tag
- Commits and pushes changes to trigger ArgoCD sync

## Configuration Options

### Update Strategies

1. **Latest**: Always use the most recent tag
2. **Semantic**: Use the highest semantic version
3. **Digest**: Use a specific image digest for reproducibility

### Update Intervals

```yaml
# Check every 5 minutes
argocd-image-updater.argoproj.io/update-interval: "5m"

# Check every hour
argocd-image-updater.argoproj.io/update-interval: "1h"
```

### Tag Patterns

```yaml
# Match semantic versions
tradestreamhq/candle-ingestor=~^v[0-9]+\.[0-9]+\.[0-9]+.*$

# Match specific pattern
tradestreamhq/candle-ingestor=~^v[0-9]+\.[0-9]+\.[0-9]+-main$
```

## Benefits of This Approach

1. **Automated Updates**: No manual intervention required
2. **Consistent Tagging**: All services use the same tag
3. **Rollback Capability**: ArgoCD maintains deployment history
4. **GitOps Compliance**: All changes are tracked in Git
5. **Reduced CI Complexity**: Remove tag update logic from GitHub Actions

## Migration from Current Workflow

### Current Workflow Issues
- Manual tag updates in `values.yaml`
- Complex yq commands in GitHub Actions
- Risk of tag mismatches between services

### ArgoCD Solution
- Automatic tag detection and updates
- Centralized image management
- Consistent deployment across all services

## Troubleshooting

### Common Issues

1. **Image Not Found**: Check repository permissions and image names
2. **Tag Not Updated**: Verify tag patterns and update intervals
3. **Sync Failures**: Check ArgoCD logs and application status

### Debugging Commands

```bash
# Check ArgoCD application status
argocd app get tradestream

# View application logs
argocd app logs tradestream

# Check image updater status
kubectl get pods -n argocd -l app.kubernetes.io/name=argocd-image-updater
```

## Next Steps

1. Choose the method that best fits your workflow
2. Update your Helm templates to use the new image tag references
3. Deploy the ArgoCD application
4. Test the automatic update process
5. Remove manual tag update logic from your GitHub Actions workflow

## References

- [ArgoCD Image Updater Documentation](https://argocd-image-updater.readthedocs.io/)
- [ArgoCD Application Specification](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/)
- [Akuity Blog: ArgoCD Build Environment Examples](https://akuity.io/blog/argo-cd-build-environment-examples) 