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
        "//services/auth_api:auth_service_lib",
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
    name = "pipeline_metrics",
    srcs = [
        "__init__.py",
        "pipeline_metrics.py",
    ],
)

py_test(
    name = "pipeline_metrics_test",
    srcs = ["pipeline_metrics_test.py"],
    deps = [
        ":pipeline_metrics",
        "//third_party/python:pytest",
    ],
)

py_library(
    name = "circuit_breaker",
    srcs = [
        "__init__.py",
        "circuit_breaker.py",
    ],
)

py_test(
    name = "circuit_breaker_test",
    srcs = ["circuit_breaker_test.py"],
    deps = [
        ":circuit_breaker",
        "//third_party/python:pytest",
    ],
)

py_library(
    name = "dead_letter_queue",
    srcs = [
        "__init__.py",
        "dead_letter_queue.py",
    ],
)

py_test(
    name = "dead_letter_queue_test",
    srcs = ["dead_letter_queue_test.py"],
    deps = [
        ":dead_letter_queue",
        ":pipeline_metrics",
        "//third_party/python:pytest",
    ],
)

py_library(
    name = "alerting",
    srcs = [
        "__init__.py",
        "alerting.py",
    ],
)

py_test(
    name = "alerting_test",
    srcs = ["alerting_test.py"],
    deps = [
        ":alerting",
        "//third_party/python:pytest",
    ],
)

py_library(
    name = "mcp_server_base",
    srcs = [
        "__init__.py",
        "mcp_server_base.py",
    ],
    deps = [
        "//third_party/python:mcp",
    ],
)

py_test(
    name = "mcp_server_base_test",
    srcs = ["mcp_server_base_test.py"],
    deps = [
        ":mcp_server_base",
        "//third_party/python:mcp",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
    ],
)

py_library(
    name = "evolution",
    srcs = [
        "__init__.py",
        "evolution.py",
    ],
)

py_test(
    name = "evolution_test",
    srcs = ["evolution_test.py"],
    deps = [
        ":evolution",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
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

py_library(
    name = "mcp_errors",
    srcs = [
        "__init__.py",
        "mcp_errors.py",
    ],
)

py_library(
    name = "mcp_pagination",
    srcs = [
        "__init__.py",
        "mcp_pagination.py",
    ],
)

py_library(
    name = "mcp_cache",
    srcs = [
        "__init__.py",
        "mcp_cache.py",
    ],
)

py_library(
    name = "mcp_metadata",
    srcs = [
        "__init__.py",
        "mcp_metadata.py",
    ],
    deps = [
        "//third_party/python:mcp",
    ],
)

py_test(
    name = "mcp_errors_test",
    srcs = ["mcp_errors_test.py"],
    deps = [
        ":mcp_errors",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "mcp_pagination_test",
    srcs = ["mcp_pagination_test.py"],
    deps = [
        ":mcp_pagination",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "mcp_cache_test",
    srcs = ["mcp_cache_test.py"],
    deps = [
        ":mcp_cache",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "mcp_metadata_test",
    srcs = ["mcp_metadata_test.py"],
    deps = [
        ":mcp_metadata",
        "//third_party/python:mcp",
        "//third_party/python:pytest",
    ],
)
