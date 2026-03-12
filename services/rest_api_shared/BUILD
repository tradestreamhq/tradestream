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
    name = "circuit_breaker",
    srcs = [
        "__init__.py",
        "circuit_breaker.py",
    ],
)

py_library(
    name = "retry",
    srcs = [
        "__init__.py",
        "retry.py",
    ],
)

py_library(
    name = "error_middleware",
    srcs = [
        "__init__.py",
        "error_middleware.py",
    ],
    deps = [
        ":circuit_breaker",
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

py_test(
    name = "circuit_breaker_test",
    srcs = ["circuit_breaker_test.py"],
    deps = [
        ":circuit_breaker",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
    ],
)

py_test(
    name = "retry_test",
    srcs = ["retry_test.py"],
    deps = [
        ":retry",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
    ],
)

py_test(
    name = "error_middleware_test",
    srcs = ["error_middleware_test.py"],
    deps = [
        ":circuit_breaker",
        ":error_middleware",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pydantic",
        "//third_party/python:pytest",
    ],
)
