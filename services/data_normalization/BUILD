load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "models_lib",
    srcs = ["models.py"],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/python:pydantic",
    ],
)

py_library(
    name = "exchange_adapters_lib",
    srcs = ["exchange_adapters.py"],
    visibility = ["//visibility:public"],
    deps = [
        ":models_lib",
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "normalizer_lib",
    srcs = ["normalizer.py"],
    visibility = ["//visibility:public"],
    deps = [
        ":exchange_adapters_lib",
        ":models_lib",
        "//third_party/python:absl_py",
    ],
)

py_test(
    name = "models_test",
    srcs = ["models_test.py"],
    deps = [
        ":models_lib",
    ],
)

py_test(
    name = "exchange_adapters_test",
    srcs = ["exchange_adapters_test.py"],
    deps = [
        ":exchange_adapters_lib",
        ":models_lib",
    ],
)

py_test(
    name = "normalizer_test",
    srcs = ["normalizer_test.py"],
    deps = [
        ":normalizer_lib",
        ":models_lib",
    ],
)
