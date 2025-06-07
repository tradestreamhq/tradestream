load("@rules_java//java:defs.bzl", "java_library")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility = [
    "//src/main/java/com/verlumen/tradestream/discovery:__pkg__",
    "//src/main/java/com/verlumen/tradestream/postgres:__pkg__",
    "//src/test/java/com/verlumen/tradestream/discovery:__pkg__",
])

kt_jvm_library(
    name = "data_source_factory",
    srcs = ["DataSourceFactory.kt"],
)
