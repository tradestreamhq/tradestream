load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "simulator_lib",
    srcs = ["simulator.py"],
    visibility = ["//visibility:public"],
)

py_test(
    name = "simulator_test",
    srcs = ["simulator_test.py"],
    deps = [
        ":simulator_lib",
        "//third_party/python:pytest",
    ],
)
