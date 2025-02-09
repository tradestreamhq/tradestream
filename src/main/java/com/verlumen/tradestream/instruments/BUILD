load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "currency",
    srcs = ["Currency.java"],
    deps = [
        "//third_party:auto_value",
    ],
)

java_library(
    name = "currency_pair",
    srcs = ["CurrencyPair.java"],
    deps = [
        "//third_party:auto_value",
        "//third_party:guava",
        ":currency",
    ],
)
