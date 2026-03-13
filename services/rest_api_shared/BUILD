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

py_library(
    name = "rate_limiter",
    srcs = [
        "__init__.py",
        "rate_limiter.py",
    ],
    deps = [
        "//third_party/python:fastapi",
    ],
)

py_library(
    name = "request_validation",
    srcs = [
        "__init__.py",
        "request_validation.py",
    ],
    deps = [
        "//third_party/python:fastapi",
    ],
)

py_library(
    name = "cors",
    srcs = [
        "__init__.py",
        "cors.py",
    ],
    deps = [
        "//third_party/python:fastapi",
    ],
)

py_library(
    name = "request_logging",
    srcs = [
        "__init__.py",
        "request_logging.py",
    ],
    deps = [
        "//third_party/python:fastapi",
    ],
)

py_library(
    name = "middleware",
    srcs = [
        "__init__.py",
        "middleware.py",
    ],
    deps = [
        ":cors",
        ":rate_limiter",
        ":request_logging",
        ":request_validation",
        "//services/shared:auth",
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

py_test(
    name = "rate_limiter_test",
    srcs = ["rate_limiter_test.py"],
    deps = [
        ":rate_limiter",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "request_validation_test",
    srcs = ["request_validation_test.py"],
    deps = [
        ":request_validation",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "cors_test",
    srcs = ["cors_test.py"],
    deps = [
        ":cors",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "request_logging_test",
    srcs = ["request_logging_test.py"],
    deps = [
        ":request_logging",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "middleware_test",
    srcs = ["middleware_test.py"],
    deps = [
        ":middleware",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
    ],
)
