load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "risk_management_lib",
    srcs = ["risk_management.py"],
    visibility = ["//services:__subpackages__"],
)

py_test(
    name = "risk_management_test",
    srcs = ["risk_management_test.py"],
    deps = [
        ":risk_management_lib",
        "//third_party/python:pytest",
    ],
)

filegroup(
    name = "config",
    srcs = ["default_config.yaml"],
    visibility = ["//visibility:public"],
)
