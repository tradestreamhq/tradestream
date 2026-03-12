load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "models_lib",
    srcs = ["models.py"],
    visibility = ["//visibility:public"],
)

py_library(
    name = "journal_lib",
    srcs = ["journal.py"],
    deps = [
        ":models_lib",
        "//third_party/python:absl_py",
    ],
    visibility = ["//visibility:public"],
)

py_library(
    name = "exporter_lib",
    srcs = ["exporter.py"],
    deps = [
        ":models_lib",
    ],
    visibility = ["//visibility:public"],
)

py_library(
    name = "service_lib",
    srcs = ["service.py"],
    deps = [
        ":exporter_lib",
        ":journal_lib",
        "//services/shared:auth",
        "//third_party/python:flask",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":journal_lib",
        ":service_lib",
        "//third_party/python:absl_py",
    ],
)

py_test(
    name = "service_test",
    srcs = ["service_test.py"],
    deps = [
        ":journal_lib",
        ":models_lib",
        ":service_lib",
        "//third_party/python:pytest",
    ],
)
