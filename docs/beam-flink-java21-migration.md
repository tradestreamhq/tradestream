# Stream Processing Framework Migration: Java 21 Support

**Issue:** #1557
**Date:** 2026-03-20
**Status:** In Progress

## Current State

| Component | Version | Java 21 Status |
|-----------|---------|----------------|
| Apache Beam SDK | 2.62.0 | Compatible |
| Beam Flink Runner | 1.18 (beam-runners-flink-1.18:2.62.0) | Compatible |
| Flink Docker Image | flink:2.2-java21 | Compatible |
| Bazel Java toolchain | remotejdk_21 | Configured |
| JAVA_LANGUAGE_LEVEL | 21 | Set |
| Kafka Clients | 3.6.1 -> 3.8.1 | Upgraded |
| google-java-format CI | Java 17 -> 21 | Fixed |

## Audit Findings

### No Breaking Issues Found

The codebase scan found **no use of**:
- `sun.*` or `com.sun.*` internal APIs (except google-java-format's JDK compiler exports, which use `--add-exports`)
- Deprecated reflection hacks (`setAccessible` on JDK internals)
- `--illegal-access` flags
- Incompatible serialization patterns

### Changes Made in This PR

1. **CI Workflow** (`.github/workflows/format-java-code.yaml`)
   - Updated `java-version` from `"17"` to `"21"` to match project config

2. **Kafka Clients** (`MODULE.bazel`)
   - Upgraded from `3.6.1` to `3.8.1` for better Java 21 runtime support

3. **Flink JVM Options** (`charts/tradestream/values.yaml`)
   - Added `--add-opens=java.base/java.lang=ALL-UNNAMED` and
     `--add-opens=java.base/java.util=ALL-UNNAMED` to both
     JobManager and TaskManager JVM options
   - Added `-XX:+IgnoreUnrecognizedVMOptions` for forward compatibility

## Migration Path: Beam 2.62+ on Flink 1.18 with Java 21

### Phase 1: Foundation (This PR)
- [x] Confirm Bazel toolchain targets Java 21
- [x] Confirm Docker base images use Java 21
- [x] Update CI to use Java 21
- [x] Upgrade Kafka clients for Java 21 compatibility
- [x] Add Java 21 module flags to Flink Kubernetes config
- [x] Audit all Beam pipeline code for compatibility

### Phase 2: Validation (Next)
- [ ] Run full Beam pipeline test suite with `DirectRunner`
- [ ] Deploy to staging with `FlinkRunner` on Java 21
- [ ] Monitor for `IllegalAccessError` or module access warnings
- [ ] Benchmark serialization performance (Java 21 may show improvements)

### Phase 3: Beam Version Tracking
- [ ] Track Beam 2.63+ releases for Flink 2.x native runner support
- [ ] Evaluate `beam-runners-flink-2.0` when available
- [ ] Consider Flink SQL integration for simpler pipelines

### Phase 4: Java 21 Feature Adoption
- [ ] Adopt virtual threads for I/O-heavy DoFns (if Beam supports)
- [ ] Use pattern matching in pipeline transform logic
- [ ] Use record classes for pipeline configuration DTOs
- [ ] Evaluate sealed classes for strategy type hierarchies

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Module access errors at runtime | Low | High | `--add-opens` flags in Flink config |
| Kafka serialization issues | Low | Medium | Upgraded to 3.8.1 |
| google-java-format incompatibility | Very Low | Low | Using `--add-exports` flags |
| Beam/Flink version incompatibility | Very Low | High | Using officially supported versions |

## Dependencies Compatibility Matrix

All critical dependencies have been verified compatible with Java 21:

- Google Guava 33.4.0-jre
- Google Guice 7.0.0
- Protobuf Java 4.29.2
- gRPC Java 1.78.0
- Ta4j 0.22.0
- Jenetics 7.2.0
- InfluxDB Client 7.3.0
- PostgreSQL Driver 42.7.6
- Flyway 10.21.0
