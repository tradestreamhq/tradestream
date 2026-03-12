load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "correlation_analysis_lib",
    srcs = ["correlation_analysis.py"],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/python:numpy",
    ],
)

py_test(
    name = "correlation_analysis_test",
    srcs = ["correlation_analysis_test.py"],
    deps = [
        ":correlation_analysis_lib",
        "//third_party/python:numpy",
        "//third_party/python:pytest",
    ],
)
