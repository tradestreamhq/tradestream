load("@rules_java//java:defs.bzl", "java_test")

package(default_visibility = ["//visibility:public"])

java_test(
    name = "FlywayMigrationTest",
    srcs = ["FlywayMigrationTest.java"],
    data = ["//database:migrations"],
    test_class = "com.verlumen.tradestream.database.FlywayMigrationTest",
    deps = [
        "//third_party/java:flyway_core",
        "//third_party/java:flyway_postgresql",
        "//third_party/java:h2",
        "//third_party/java:junit",
        "//third_party/java:truth",
    ],
)
