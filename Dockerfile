# ============================================
# Stage 1: Builder — compile with Bazel
# ============================================
FROM eclipse-temurin:21-jdk AS builder

# Install Bazel via Bazelisk
ARG BAZELISK_VERSION=1.25.0
ADD https://github.com/bazelbuild/bazelisk/releases/download/v${BAZELISK_VERSION}/bazelisk-linux-amd64 /usr/local/bin/bazel
RUN chmod +x /usr/local/bin/bazel

# Install Python 3.13 (needed by rules_python)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy dependency manifests first for layer caching
COPY MODULE.bazel MODULE.bazel.lock WORKSPACE BUILD requirements.in requirements_lock.txt ./
COPY platforms/ platforms/
COPY third_party/ third_party/

# Fetch external dependencies (cacheable layer)
RUN bazel fetch //... 2>/dev/null || true

# Copy the full source tree
COPY . .

# Build the deployable jar
RUN bazel build //src/main/java/com/verlumen/tradestream/... --jobs=auto

# ============================================
# Stage 2: Production — minimal JRE image
# ============================================
FROM eclipse-temurin:21-jre-jammy AS production

RUN groupadd --gid 1001 tradestream \
    && useradd --uid 1001 --gid tradestream --shell /bin/bash --create-home tradestream

WORKDIR /app

# Copy built artifacts from builder
COPY --from=builder /build/bazel-bin/src/main/java/com/verlumen/tradestream/ ./lib/

# Copy database migrations
COPY --from=builder /build/database/ ./database/

# Install health-check dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

USER tradestream

EXPOSE 8080 50051

ENTRYPOINT ["java", "-jar"]
CMD ["lib/tradestream_deploy.jar"]
