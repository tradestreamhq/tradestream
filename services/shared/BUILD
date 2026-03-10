load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "decision_logger",
    srcs = [
        "__init__.py",
        "decision_logger.py",
    ],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:psycopg2_binary",
    ],
)

py_test(
    name = "decision_logger_test",
    srcs = ["decision_logger_test.py"],
    deps = [
        ":decision_logger",
        "//third_party/python:pytest",
    ],
)
