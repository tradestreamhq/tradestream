# Workflow Simplification: Removing Manual Tag Updates

## Overview

The GitHub Actions workflow has been simplified by removing manual `values.yaml` updates since ArgoCD Image Updater now handles this automatically.

## What Was Removed

### ❌ **Removed Steps:**

1. **Install yq** - No longer needed for manual YAML manipulation
2. **Update values.yaml with new image tags** - Complex yq command that updated all service tags
3. **Commit and Push All Changes** - Manual Git operations for values.yaml

### ✅ **What Remains:**

1. **Semantic versioning** - Still generates proper version tags
2. **Docker image builds** - All services are still built and pushed
3. **MODULE.bazel updates** - Still needed for Bazel version tracking
4. **Git tag creation** - Still creates semantic version tags

## Before vs After

### **Before (Original Workflow):**
```yaml
# Complex manual tag updates
- name: Install yq
  run: |
    sudo wget -O /usr/bin/yq https://github.com/mikefarah/yq/releases/download/v4.35.1/yq_linux_amd64
    sudo chmod +x /usr/bin/yq

- name: Update values.yaml with new image tags
  run: |
    yq eval-all '
      . as $item ireduce ({}; . * $item ) |
      .["${{ env.CANDLE_INGESTOR_SECTION_KEY }}"].image.repository = "${{ env.CANDLE_INGESTOR_REPO }}" |
      .["${{ env.CANDLE_INGESTOR_SECTION_KEY }}"].image.tag = "${{ steps.version.outputs.version_tag }}" |
      # ... 6 more services with similar lines
    ' charts/tradestream/values.yaml > charts/tradestream/values.yaml.tmp
    mv charts/tradestream/values.yaml.tmp charts/tradestream/values.yaml

- name: Commit and Push All Changes
  run: |
    git add charts/tradestream/values.yaml MODULE.bazel
    git commit -m "Bump version to ${{ steps.version.outputs.version_tag }}"
    git push https://$GITHUB_ACTOR:${{ secrets.ACTIONS_TOKEN }}@github.com/${{ github.repository }} HEAD:${{ github.ref }}
```

### **After (Simplified Workflow):**
```yaml
# Only MODULE.bazel updates (still needed)
- name: Update MODULE.bazel version
  run: |
    sed -i.bak '/^module(/,/^)/ s/\(version\s*=\s*"\)[^"]\+"/\1'"${{ steps.version.outputs.version_tag }}"'"/' MODULE.bazel

- name: Commit and Push MODULE.bazel Changes
  run: |
    git add MODULE.bazel
    git commit -m "Bump version to ${{ steps.version.outputs.version_tag }}"
    git push https://$GITHUB_ACTOR:${{ secrets.ACTIONS_TOKEN }}@github.com/${{ github.repository }} HEAD:${{ github.ref }}

# Informational step
- name: Notify ArgoCD Deployment
  run: |
    echo "✅ Images pushed with tag: ${{ steps.version.outputs.version_tag }}"
    echo "🔄 ArgoCD Image Updater will automatically detect and deploy the new images within 2-5 minutes"
```

## Benefits of Simplification

### **1. Reduced Complexity**
- ❌ **Before**: 40+ lines of complex yq commands
- ✅ **After**: Simple sed command for MODULE.bazel only

### **2. Fewer Dependencies**
- ❌ **Before**: Required yq installation and complex YAML manipulation
- ✅ **After**: Uses only basic shell commands

### **3. Reduced Risk**
- ❌ **Before**: Risk of tag mismatches between services
- ✅ **After**: ArgoCD ensures all services use the same tag

### **4. Better Separation of Concerns**
- **CI Pipeline**: Builds and pushes images
- **ArgoCD**: Handles deployment and tag management

### **5. Faster Execution**
- ❌ **Before**: ~2-3 minutes for manual updates
- ✅ **After**: ~30 seconds for MODULE.bazel update only

## How It Works Now

1. **GitHub Actions** builds and pushes images with semantic version tags
2. **ArgoCD Image Updater** detects new tags every 2 minutes
3. **ArgoCD** automatically updates `values.yaml` and deploys
4. **No manual intervention** required

## Migration Steps

1. **Replace the workflow file:**
   ```bash
   mv .github/workflows/release.yaml .github/workflows/release.yaml.backup
   mv .github/workflows/release-simplified.yaml .github/workflows/release.yaml
   ```

2. **Test the new workflow:**
   - Push a commit to trigger the workflow
   - Verify images are pushed with correct tags
   - Check that ArgoCD picks up the new tags within 2-5 minutes

3. **Monitor the deployment:**
   ```bash
   kubectl get application tradestream-dev -n argocd
   kubectl logs -n argocd deployment/argocd-image-updater -f
   ```

## Rollback Plan

If you need to rollback, you can:
1. Restore the original workflow file
2. Disable ArgoCD Image Updater annotations
3. Continue with manual tag updates

## Verification

After migration, verify that:
- ✅ Images are pushed with correct semantic version tags
- ✅ ArgoCD detects and deploys new images automatically
- ✅ All services use the same tag consistently
- ✅ Deployment happens within 2-5 minutes of image push 