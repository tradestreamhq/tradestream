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

py_library(
    name = "mcp_client",
    srcs = [
        "__init__.py",
        "mcp_client.py",
    ],
    deps = [
        "//third_party/python:requests",
    ],
)

py_library(
    name = "auth",
    srcs = [
        "__init__.py",
        "auth.py",
    ],
    deps = [
        "//third_party/python:fastapi",
        "//third_party/python:flask",
    ],
)

py_library(
    name = "model_config",
    srcs = [
        "__init__.py",
        "model_config.py",
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

py_library(
    name = "structured_logger",
    srcs = [
        "__init__.py",
        "structured_logger.py",
    ],
    deps = [
        "//third_party/python:absl_py",
    ],
)

py_test(
    name = "mcp_client_test",
    srcs = ["mcp_client_test.py"],
    deps = [
        ":mcp_client",
        "//third_party/python:pytest",
        "//third_party/python:requests",
    ],
)

py_test(
    name = "auth_test",
    srcs = ["auth_test.py"],
    deps = [
        ":auth",
        "//third_party/python:fastapi",
        "//third_party/python:flask",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "model_config_test",
    srcs = ["model_config_test.py"],
    deps = [
        ":model_config",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "structured_logger_test",
    srcs = ["structured_logger_test.py"],
    deps = [
        ":structured_logger",
        "//third_party/python:pytest",
    ],
)

py_library(
    name = "strategy_parameter_registry",
    srcs = [
        "__init__.py",
        "strategy_parameter_registry.py",
    ],
    deps = [
        "//protos:strategies_py_proto",
        "//third_party/python:protobuf",
    ],
)

py_test(
    name = "strategy_parameter_registry_test",
    srcs = ["strategy_parameter_registry_test.py"],
    deps = [
        ":strategy_parameter_registry",
        "//protos:strategies_py_proto",
        "//third_party/python:protobuf",
        "//third_party/python:pytest",
    ],
)
