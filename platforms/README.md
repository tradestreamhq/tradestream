# Platform Configurations

This directory contains platform-specific configurations and build system utilities for the TradeStream project. It includes Docker platform configurations, Bazel transition rules, and cross-platform build support.

## Production System Overview

The platforms module supports the production deployment:

- **Status**: ✅ **PRODUCTION** - Multi-platform support operational
- **Infrastructure**: Kubernetes deployment across multiple architectures
- **Container Support**: Docker multi-architecture builds
- **Build System**: Bazel cross-platform compilation
- **Deployment**: Production services running on multiple platforms

## Overview

The platforms module provides:

- **Docker platform configurations** for multi-architecture container builds
- **Bazel transition rules** for platform-specific build configurations
- **Cross-platform support** for different operating systems and architectures
- **Build system utilities** for platform-specific optimizations

## Directory Structure

```
platforms/
├── BUILD                    # Bazel build configuration
├── docker.bzl              # Docker platform utilities
├── transition.bzl          # Bazel transition rules
└── [additional platform files]
```

## Docker Platform Support

### Multi-Architecture Builds

The `docker.bzl` file provides utilities for building containers across multiple architectures:

```python
# Docker platform utilities
load("@io_bazel_rules_docker//container:container.bzl", "container_image")
load("//platforms:docker.bzl", "multi_platform_image")

# Define supported platforms
SUPPORTED_PLATFORMS = [
    "linux/amd64",
    "linux/arm64",
    "linux/arm/v7",
]

# Create multi-platform image
multi_platform_image(
    name = "candle_ingestor_image",
    base = "//platforms:python_base",
    srcs = ["//services/candle_ingestor:main"],
    platforms = SUPPORTED_PLATFORMS,
    visibility = ["//visibility:public"],
)
```

### Platform-Specific Configurations

```python
# Platform-specific build configurations
PLATFORM_CONFIGS = {
    "linux/amd64": {
        "cpu": "x86_64",
        "os": "linux",
        "arch": "amd64",
    },
    "linux/arm64": {
        "cpu": "aarch64",
        "os": "linux",
        "arch": "arm64",
    },
    "linux/arm/v7": {
        "cpu": "arm",
        "os": "linux",
        "arch": "arm",
    },
}
```

## Bazel Transition Rules

### Platform Transitions

The `transition.bzl` file defines Bazel transition rules for platform-specific builds:

```python
# Platform transition rules
def _platform_transition_impl(settings, attr):
    platform = settings["//command_line_option:platforms"]

    # Apply platform-specific settings
    if "arm64" in str(platform):
        return {
            "//command_line_option:cpu": "aarch64",
            "//command_line_option:compilation_mode": "opt",
        }
    elif "amd64" in str(platform):
        return {
            "//command_line_option:cpu": "x86_64",
            "//command_line_option:compilation_mode": "opt",
        }
    else:
        return {}

platform_transition = transition(
    implementation = _platform_transition_impl,
    inputs = ["//command_line_option:platforms"],
    outputs = [
        "//command_line_option:cpu",
        "//command_line_option:compilation_mode",
    ],
)
```

### Cross-Platform Build Rules

```python
# Cross-platform build rule
def cross_platform_binary(name, srcs, deps = [], **kwargs):
    native.cc_binary(
        name = name,
        srcs = srcs,
        deps = deps,
        **kwargs
    )

    # Create platform-specific variants
    for platform in ["linux_amd64", "linux_arm64"]:
        native.cc_binary(
            name = name + "_" + platform,
            srcs = srcs,
            deps = deps,
            target_compatible_with = ["@platforms//os:linux"],
            **kwargs
        )
```

## Platform-Specific Optimizations

### CPU Optimizations

```python
# CPU-specific optimizations
CPU_OPTIMIZATIONS = {
    "x86_64": [
        "-march=native",
        "-mtune=native",
        "-mavx2",
        "-mfma",
    ],
    "aarch64": [
        "-march=native",
        "-mtune=native",
        "-mfp16-format=ieee",
    ],
    "arm": [
        "-march=native",
        "-mtune=native",
        "-mfpu=neon",
    ],
}
```

### Memory Optimizations

```python
# Platform-specific memory settings
MEMORY_CONFIGS = {
    "linux/amd64": {
        "heap_size": "2g",
        "stack_size": "1m",
    },
    "linux/arm64": {
        "heap_size": "1g",
        "stack_size": "512k",
    },
    "linux/arm/v7": {
        "heap_size": "512m",
        "stack_size": "256k",
    },
}
```

## Container Platform Support

### Base Images

```dockerfile
# Multi-platform base images
FROM --platform=$BUILDPLATFORM python:3.13-slim as base

# Platform-specific optimizations
ARG TARGETPLATFORM
ARG BUILDPLATFORM

# Install platform-specific packages
RUN case "$TARGETPLATFORM" in \
    "linux/amd64") \
        apt-get update && apt-get install -y \
            libopenblas-dev \
            liblapack-dev \
            gfortran \
        ;; \
    "linux/arm64") \
        apt-get update && apt-get install -y \
            libopenblas-dev \
            liblapack-dev \
            gfortran \
        ;; \
    "linux/arm/v7") \
        apt-get update && apt-get install -y \
            libopenblas-dev \
            liblapack-dev \
            gfortran \
        ;; \
    esac
```

### Platform-Specific Dependencies

```python
# Platform-specific dependency management
def get_platform_dependencies(platform):
    base_deps = [
        "//third_party/python:numpy",
        "//third_party/python:pandas",
    ]

    if platform == "linux/amd64":
        return base_deps + [
            "//third_party/python:scipy",
            "//third_party/python:scikit-learn",
        ]
    elif platform == "linux/arm64":
        return base_deps + [
            "//third_party/python:scipy_arm64",
        ]
    else:
        return base_deps
```

## Build System Integration

### Bazel Platform Rules

```python
# Platform-aware build rules
def platform_aware_binary(name, srcs, deps = [], **kwargs):
    # Create platform-specific targets
    for platform in ["linux_amd64", "linux_arm64"]:
        native.py_binary(
            name = name + "_" + platform,
            srcs = srcs,
            deps = deps + get_platform_dependencies(platform),
            target_compatible_with = ["@platforms//os:linux"],
            **kwargs
        )

    # Create default target
    native.py_binary(
        name = name,
        srcs = srcs,
        deps = deps,
        **kwargs
    )
```

### Platform Detection

```python
# Platform detection utilities
def detect_platform():
    """Detect the current platform."""
    import platform

    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        if machine in ["x86_64", "amd64"]:
            return "linux/amd64"
        elif machine in ["aarch64", "arm64"]:
            return "linux/arm64"
        elif machine.startswith("arm"):
            return "linux/arm/v7"

    return "linux/amd64"  # Default fallback
```

## Testing

### Platform-Specific Tests

```python
# Platform-specific test configurations
def platform_test(name, srcs, deps = [], **kwargs):
    # Create tests for each platform
    for platform in ["linux_amd64", "linux_arm64"]:
        native.py_test(
            name = name + "_" + platform,
            srcs = srcs,
            deps = deps,
            target_compatible_with = ["@platforms//os:linux"],
            **kwargs
        )
```

### Cross-Platform Test Execution

```bash
# Run tests on multiple platforms
bazel test --platforms=@io_bazel_rules_go//go/toolchain:linux_amd64 //...
bazel test --platforms=@io_bazel_rules_go//go/toolchain:linux_arm64 //...

# Run all platform tests
bazel test --platforms=@io_bazel_rules_go//go/toolchain:linux_amd64,@io_bazel_rules_go//go/toolchain:linux_arm64 //...
```

## Production Deployment

### Multi-Platform Deployment

```yaml
# Kubernetes deployment with platform affinity
apiVersion: apps/v1
kind: Deployment
metadata:
  name: candle-ingestor
spec:
  replicas: 3
  selector:
    matchLabels:
      app: candle-ingestor
  template:
    metadata:
      labels:
        app: candle-ingestor
    spec:
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: kubernetes.io/arch
                    operator: In
                    values:
                      - amd64
                      - arm64
      containers:
        - name: candle-ingestor
          image: tradestreamhq/candle-ingestor:latest
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "500m"
```

### Platform-Specific Resource Limits

```yaml
# Platform-specific resource configurations
platformResources:
  linux/amd64:
    requests:
      memory: "1Gi"
      cpu: "500m"
    limits:
      memory: "2Gi"
      cpu: "1000m"
  linux/arm64:
    requests:
      memory: "512Mi"
      cpu: "250m"
    limits:
      memory: "1Gi"
      cpu: "500m"
  linux/arm/v7:
    requests:
      memory: "256Mi"
      cpu: "125m"
    limits:
      memory: "512Mi"
      cpu: "250m"
```

## Performance Optimization

### Platform-Specific Optimizations

```python
# Platform-specific compiler flags
def get_platform_cflags(platform):
    if platform == "linux/amd64":
        return [
            "-O3",
            "-march=native",
            "-mtune=native",
            "-mavx2",
            "-mfma",
        ]
    elif platform == "linux/arm64":
        return [
            "-O3",
            "-march=native",
            "-mtune=native",
            "-mfp16-format=ieee",
        ]
    else:
        return ["-O2"]
```

### Memory Management

```python
# Platform-specific memory management
def get_memory_config(platform):
    if platform == "linux/amd64":
        return {
            "heap_size": "2g",
            "stack_size": "1m",
            "gc_type": "g1",
        }
    elif platform == "linux/arm64":
        return {
            "heap_size": "1g",
            "stack_size": "512k",
            "gc_type": "parallel",
        }
    else:
        return {
            "heap_size": "512m",
            "stack_size": "256k",
            "gc_type": "serial",
        }
```

## Monitoring

### Platform Metrics

```python
# Platform-specific metrics collection
def collect_platform_metrics():
    import psutil
    import platform

    return {
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "cpu_count": psutil.cpu_count(),
        "memory_total": psutil.virtual_memory().total,
        "memory_available": psutil.virtual_memory().available,
    }
```

### Performance Monitoring

```python
# Platform performance monitoring
class PlatformMonitor:
    def __init__(self):
        self.platform = detect_platform()
        self.metrics = {}

    def collect_metrics(self):
        self.metrics.update(collect_platform_metrics())
        return self.metrics

    def get_platform_specific_thresholds(self):
        if self.platform == "linux/amd64":
            return {
                "cpu_threshold": 80.0,
                "memory_threshold": 85.0,
                "disk_threshold": 90.0,
            }
        else:
            return {
                "cpu_threshold": 70.0,
                "memory_threshold": 80.0,
                "disk_threshold": 85.0,
            }
```

## Troubleshooting

### Platform-Specific Issues

#### ARM64 Compatibility

```bash
# Check ARM64 compatibility
docker run --rm --platform linux/arm64 tradestreamhq/candle-ingestor:latest \
  python -c "import numpy; print('ARM64 compatible')"

# Debug ARM64 issues
docker run --rm --platform linux/arm64 -it tradestreamhq/candle-ingestor:latest bash
```

#### Cross-Platform Build Issues

```bash
# Check platform support
bazel query --output=location //platforms:all

# Debug platform transitions
bazel build --verbose_failures --platforms=@io_bazel_rules_go//go/toolchain:linux_arm64 //...
```

### Debug Commands

```bash
# Check platform configuration
bazel info --show_make_env

# List available platforms
bazel query --output=location @platforms//os:*

# Check platform-specific targets
bazel query --output=location "attr('target_compatible_with', '@platforms//os:linux', //...)"
```

## Contributing

When contributing to platform configurations:

1. **Test Cross-Platform**: Ensure changes work across all supported platforms
2. **Performance Impact**: Consider performance implications of platform-specific changes
3. **Backward Compatibility**: Maintain compatibility with existing platform configurations
4. **Documentation**: Update documentation for new platform support
5. **Testing**: Add platform-specific tests for new features

## License

This project is part of the TradeStream platform. See the root LICENSE file for details.
