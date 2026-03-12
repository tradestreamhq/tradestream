load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "models_lib",
    srcs = ["models.py"],
    visibility = ["//visibility:public"],
)

py_library(
    name = "queue_lib",
    srcs = ["queue.py"],
    deps = [
        ":models_lib",
    ],
    visibility = ["//visibility:public"],
)

py_library(
    name = "limiter_lib",
    srcs = ["limiter.py"],
    deps = [
        ":models_lib",
        ":queue_lib",
    ],
    visibility = ["//visibility:public"],
)

py_test(
    name = "models_test",
    srcs = ["models_test.py"],
    deps = [
        ":models_lib",
    ],
)

py_test(
    name = "queue_test",
    srcs = ["queue_test.py"],
    deps = [
        ":models_lib",
        ":queue_lib",
    ],
)

py_test(
    name = "limiter_test",
    srcs = ["limiter_test.py"],
    deps = [
        ":limiter_lib",
        ":models_lib",
        ":queue_lib",
    ],
)
