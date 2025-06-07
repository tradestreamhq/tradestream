load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_test")

kt_jvm_test(
    name = "PostgreSQLDataSourceFactoryTest",
    srcs = ["PostgreSQLDataSourceFactoryTest.kt"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/postgres:postgre_sql_data_source_factory",
        "//src/main/java/com/verlumen/tradestream/sql:data_source_factory",
        "//third_party/java:junit",
        "//third_party/java:postgresql",
        "//third_party/java:truth",
    ],
)
