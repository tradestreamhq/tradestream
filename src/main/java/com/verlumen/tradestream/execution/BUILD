load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "execution_module",
    srcs = ["ExecutionModule.java"],
    deps = [
        "//third_party:auto_value",
        "//third_party:guice",
        ":run_mode",
    ],
)

java_library(
    name = "run_mode",
    srcs = ["RunMode.java"],
)
