load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

kt_jvm_library(
    name = "postgre_sql_bulk_copier_factory",
    srcs = ["PostgreSQLBulkCopierFactory.kt"],
    visibility = [
        "//src/main/java/com/verlumen/tradestream/discovery:__pkg__",
        "//src/test/java/com/verlumen/tradestream/discovery:__pkg__",
        "//src/test/java/com/verlumen/tradestream/postgres:__pkg__",
    ],
    deps = [
        "//src/main/java/com/verlumen/tradestream/sql:bulk_copier_factory",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:postgresql",
    ],
)

kt_jvm_library(
    name = "postgre_sql_data_source_factory",
    srcs = ["PostgreSQLDataSourceFactory.kt"],
    visibility = [
        "//src/main/java/com/verlumen/tradestream/discovery:__pkg__",
        "//src/test/java/com/verlumen/tradestream/discovery:__pkg__",
        "//src/test/java/com/verlumen/tradestream/postgres:__pkg__",
    ],
    deps = [
        "//src/main/java/com/verlumen/tradestream/sql:data_source_factory",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:postgresql",
    ],
)

kt_jvm_library(
    name = "postgres_module",
    srcs = ["PostgresModule.kt"],
    visibility = [
        "//src/main/java/com/verlumen/tradestream/discovery:__pkg__",
    ],
    deps = [
        ":postgre_sql_bulk_copier_factory",
        ":postgre_sql_data_source_factory",
        "//src/main/java/com/verlumen/tradestream/sql:bulk_copier_factory",
        "//src/main/java/com/verlumen/tradestream/sql:data_source_factory",
        "//third_party/java:guice",
    ],
)
