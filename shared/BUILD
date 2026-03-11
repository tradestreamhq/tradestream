load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "config",
    srcs = ["config.py"],
)

py_test(
    name = "config_test",
    srcs = ["config_test.py"],
    deps = [
        ":config",
    ],
)
