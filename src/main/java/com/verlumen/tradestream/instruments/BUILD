load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "currency",
    srcs = ["Currency.java"],
    deps = [
        "//:autovalue",
    ],
)

java_library(
    name = "currency_pair",
    srcs = ["CurrencyPair.java"],
    deps = [
        "@maven//:com_google_guava_guava",
        "//:autovalue",
        ":currency",
    ],
)
