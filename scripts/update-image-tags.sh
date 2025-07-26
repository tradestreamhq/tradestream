#!/bin/bash

# Script to update image tags in values.yaml with the latest tag
# This can be used with ArgoCD or as part of your CI/CD pipeline

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get the latest tag from Git
get_latest_tag() {
    local latest_tag
    latest_tag=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
    
    if [ -z "$latest_tag" ]; then
        print_warning "No Git tags found. Using default tag."
        latest_tag="v1.0.4-main"
    fi
    
    echo "$latest_tag"
}

# Update values.yaml with the latest tag
update_values_yaml() {
    local tag="$1"
    local values_file="charts/tradestream/values.yaml"
    
    print_status "Updating $values_file with tag: $tag"
    
    # Check if yq is available
    if ! command -v yq &> /dev/null; then
        print_error "yq is not installed. Please install yq to use this script."
        exit 1
    fi
    
    # Create backup
    cp "$values_file" "${values_file}.backup"
    
    # Update the global imageTag
    yq eval-all '
        . as $item ireduce ({}; . * $item ) |
        .global.imageTag = "'$tag'"
    ' "$values_file" > "${values_file}.tmp"
    
    # Update individual service tags
    yq eval-all '
        . as $item ireduce ({}; . * $item ) |
        .candleIngestor.image.tag = "'$tag'" |
        .topCryptoUpdaterCronjob.image.tag = "'$tag'" |
        .strategyDiscoveryRequestFactory.image.tag = "'$tag'" |
        .strategyDiscoveryPipeline.image.tag = "'$tag'" |
        .strategyConsumer.image.tag = "'$tag'" |
        .strategyMonitorApi.image.tag = "'$tag'" |
        .strategyMonitorUi.image.tag = "'$tag'"
    ' "${values_file}.tmp" > "$values_file"
    
    # Clean up temp file
    rm "${values_file}.tmp"
    
    print_status "Successfully updated $values_file"
}

# Commit and push changes (optional)
commit_changes() {
    local tag="$1"
    
    if [ "$COMMIT_CHANGES" = "true" ]; then
        print_status "Committing changes with tag: $tag"
        
        git add charts/tradestream/values.yaml
        git commit -m "Update image tags to $tag" || {
            print_warning "No changes to commit"
            return 0
        }
        
        if [ "$PUSH_CHANGES" = "true" ]; then
            print_status "Pushing changes to remote repository"
            git push
        else
            print_warning "Changes committed but not pushed. Use --push to push changes."
        fi
    else
        print_status "Changes made to values.yaml but not committed. Use --commit to commit changes."
    fi
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --tag TAG           Use specific tag instead of detecting from Git"
    echo "  --commit            Commit changes to Git repository"
    echo "  --push              Push changes to remote repository (requires --commit)"
    echo "  --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Update with latest Git tag"
    echo "  $0 --tag v1.0.5                      # Update with specific tag"
    echo "  $0 --commit                          # Update and commit changes"
    echo "  $0 --commit --push                   # Update, commit, and push changes"
}

# Parse command line arguments
COMMIT_CHANGES=false
PUSH_CHANGES=false
SPECIFIC_TAG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --tag)
            SPECIFIC_TAG="$2"
            shift 2
            ;;
        --commit)
            COMMIT_CHANGES=true
            shift
            ;;
        --push)
            PUSH_CHANGES=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
main() {
    print_status "Starting image tag update process"
    
    # Get the tag to use
    if [ -n "$SPECIFIC_TAG" ]; then
        TAG="$SPECIFIC_TAG"
        print_status "Using specified tag: $TAG"
    else
        TAG=$(get_latest_tag)
        print_status "Detected latest tag: $TAG"
    fi
    
    # Update values.yaml
    update_values_yaml "$TAG"
    
    # Commit changes if requested
    commit_changes "$TAG"
    
    print_status "Image tag update completed successfully"
}

# Run main function
main "$@" 