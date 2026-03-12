load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "models_lib",
    srcs = ["models.py"],
)

py_library(
    name = "delivery_lib",
    srcs = ["delivery.py"],
    deps = [
        ":models_lib",
        "//third_party/python:absl_py",
        "//third_party/python:requests",
    ],
)

py_library(
    name = "service_lib",
    srcs = ["service.py"],
    deps = [
        ":delivery_lib",
        ":models_lib",
        "//third_party/python:absl_py",
    ],
)

py_test(
    name = "webhook_test",
    srcs = ["webhook_test.py"],
    deps = [
        ":delivery_lib",
        ":models_lib",
        ":service_lib",
        "//third_party/python:pytest",
        "//third_party/python:requests",
    ],
)
