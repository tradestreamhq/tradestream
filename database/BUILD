load("@rules_java//java:defs.bzl", "java_binary", "java_library")

package(default_visibility = ["//visibility:public"])

# SQL migration files for Flyway
filegroup(
    name = "migrations",
    srcs = glob(["migrations/V*.sql"]),
)

# Library for running Flyway migrations programmatically
java_library(
    name = "flyway_migrator",
    srcs = ["FlywayMigrator.java"],
    resources = [":migrations"],
    deps = [
        "//third_party/java:flyway_core",
        "//third_party/java:flyway_postgresql",
        "//third_party/java:postgresql",
    ],
)

# CLI tool for running migrations
java_binary(
    name = "migrate",
    main_class = "com.verlumen.tradestream.database.FlywayMigrator",
    runtime_deps = [
        ":flyway_migrator",
    ],
)
