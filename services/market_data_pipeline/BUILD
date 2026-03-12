load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "schema_lib",
    srcs = ["schema.py"],
    visibility = ["//visibility:public"],
)

py_library(
    name = "adapters_lib",
    srcs = ["adapters.py"],
    visibility = ["//visibility:public"],
    deps = [
        ":schema_lib",
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "validation_lib",
    srcs = ["validation.py"],
    visibility = ["//visibility:public"],
    deps = [
        ":schema_lib",
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "replay_lib",
    srcs = ["replay.py"],
    visibility = ["//visibility:public"],
    deps = [
        ":adapters_lib",
        ":schema_lib",
        ":validation_lib",
        "//third_party/python:absl_py",
    ],
)

py_test(
    name = "pipeline_test",
    srcs = ["pipeline_test.py"],
    data = glob(["testdata/**"]),
    deps = [
        ":adapters_lib",
        ":replay_lib",
        ":schema_lib",
        ":validation_lib",
    ],
)
