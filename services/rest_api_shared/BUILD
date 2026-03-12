load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "responses",
    srcs = [
        "__init__.py",
        "responses.py",
    ],
    deps = [
        "//third_party/python:fastapi",
    ],
)

py_library(
    name = "pagination",
    srcs = [
        "__init__.py",
        "pagination.py",
    ],
    deps = [
        "//third_party/python:fastapi",
    ],
)

py_library(
    name = "health",
    srcs = [
        "__init__.py",
        "health.py",
    ],
    deps = [
        "//third_party/python:fastapi",
    ],
)

py_library(
    name = "mcp_wrapper",
    srcs = [
        "__init__.py",
        "mcp_wrapper.py",
    ],
    deps = [
        "//third_party/python:httpx",
        "//third_party/python:mcp",
    ],
)

py_test(
    name = "responses_test",
    srcs = ["responses_test.py"],
    deps = [
        ":responses",
        "//third_party/python:pytest",
    ],
)
