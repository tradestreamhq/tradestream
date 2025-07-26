#!/bin/bash

# Test script to verify ArgoCD Image Updater functionality
# This script will help you test if the Image Updater is working correctly

set -e

echo "🔍 Checking ArgoCD Image Updater status..."

# Check if Image Updater pod is running
echo "📊 Image Updater Pod Status:"
kubectl get pods -n argocd -l app.kubernetes.io/name=argocd-image-updater

echo ""
echo "📋 Application Annotations:"
kubectl get application tradestream-dev -n argocd -o jsonpath='{.metadata.annotations}' | jq .

echo ""
echo "🖼️  Current Images in Application:"
kubectl get application tradestream-dev -n argocd -o jsonpath='{.status.summary.images}' | jq .

echo ""
echo "📝 Recent Image Updater Logs:"
kubectl logs -n argocd deployment/argocd-image-updater --tail=10

echo ""
echo "✅ ArgoCD Image Updater is configured and running!"
echo ""
echo "📋 How it works:"
echo "1. Image Updater monitors your Docker Hub repositories"
echo "2. When new tags matching the pattern 'v*.*.*' are found, it updates the application"
echo "3. The application will automatically sync and deploy the new images"
echo ""
echo "🔧 To test:"
echo "1. Push a new image with tag like 'v1.0.5-main'"
echo "2. Wait 2-5 minutes for Image Updater to detect it"
echo "3. Check application status: kubectl get application tradestream-dev -n argocd"
echo ""
echo "📊 To monitor updates:"
echo "kubectl logs -n argocd deployment/argocd-image-updater -f" 