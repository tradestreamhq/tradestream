load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "config_lib",
    srcs = [
        "__init__.py",
        "config.py",
    ],
)

py_library(
    name = "signal_fusion_lib",
    srcs = [
        "__init__.py",
        "signal_fusion.py",
    ],
)

py_library(
    name = "decision_models_lib",
    srcs = [
        "__init__.py",
        "decision_models.py",
    ],
)

py_library(
    name = "risk_manager_lib",
    srcs = [
        "__init__.py",
        "risk_manager.py",
    ],
    deps = [
        ":config_lib",
        ":signal_fusion_lib",
    ],
)

py_library(
    name = "kill_switch_lib",
    srcs = [
        "__init__.py",
        "kill_switch.py",
    ],
)

py_library(
    name = "retry_lib",
    srcs = [
        "__init__.py",
        "retry.py",
    ],
)

py_library(
    name = "metrics_lib",
    srcs = [
        "__init__.py",
        "metrics.py",
    ],
)

py_library(
    name = "adaptive_scheduler_lib",
    srcs = [
        "__init__.py",
        "adaptive_scheduler.py",
    ],
)

py_library(
    name = "db_persistence_lib",
    srcs = [
        "__init__.py",
        "db_persistence.py",
    ],
)

py_library(
    name = "signal_cache_lib",
    srcs = [
        "__init__.py",
        "signal_cache.py",
    ],
)

py_library(
    name = "batch_processor_lib",
    srcs = [
        "__init__.py",
        "batch_processor.py",
    ],
)

py_library(
    name = "retention_lib",
    srcs = [
        "__init__.py",
        "retention.py",
    ],
)

py_library(
    name = "coordinator_lib",
    srcs = [
        "__init__.py",
        "coordinator.py",
    ],
    deps = [
        ":adaptive_scheduler_lib",
        ":batch_processor_lib",
        ":config_lib",
        ":db_persistence_lib",
        ":decision_models_lib",
        ":metrics_lib",
        ":retry_lib",
        ":risk_manager_lib",
        ":signal_cache_lib",
        ":signal_fusion_lib",
        "//services/shared:circuit_breaker",
        "//services/shared:mcp_client",
    ],
)

py_library(
    name = "dashboard_lib",
    srcs = [
        "__init__.py",
        "dashboard.py",
    ],
    deps = [
        ":metrics_lib",
        "//third_party/python:fastapi",
        "//third_party/python:pydantic",
    ],
)

py_library(
    name = "runner_lib",
    srcs = [
        "__init__.py",
        "runner.py",
    ],
    deps = [
        ":config_lib",
        ":coordinator_lib",
        ":dashboard_lib",
        ":kill_switch_lib",
        ":metrics_lib",
        "//services/shared:circuit_breaker",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":config_lib",
        ":dashboard_lib",
        ":runner_lib",
        "//third_party/python:absl_py",
        "//third_party/python:redis",
        "//third_party/python:uvicorn",
    ],
)

py_test(
    name = "signal_fusion_test",
    srcs = ["signal_fusion_test.py"],
    deps = [
        ":signal_fusion_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "risk_manager_test",
    srcs = ["risk_manager_test.py"],
    deps = [
        ":config_lib",
        ":risk_manager_lib",
        ":signal_fusion_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "decision_models_test",
    srcs = ["decision_models_test.py"],
    deps = [
        ":decision_models_lib",
        ":signal_fusion_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "kill_switch_test",
    srcs = ["kill_switch_test.py"],
    deps = [
        ":config_lib",
        ":kill_switch_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "coordinator_test",
    srcs = ["coordinator_test.py"],
    deps = [
        ":config_lib",
        ":coordinator_lib",
        ":signal_fusion_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "retry_test",
    srcs = ["retry_test.py"],
    deps = [
        ":retry_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "adaptive_scheduler_test",
    srcs = ["adaptive_scheduler_test.py"],
    deps = [
        ":adaptive_scheduler_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "db_persistence_test",
    srcs = ["db_persistence_test.py"],
    deps = [
        ":db_persistence_lib",
        ":decision_models_lib",
        ":signal_fusion_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "metrics_test",
    srcs = ["metrics_test.py"],
    deps = [
        ":metrics_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "runner_test",
    srcs = ["runner_test.py"],
    deps = [
        ":config_lib",
        ":coordinator_lib",
        ":runner_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "dashboard_test",
    srcs = ["dashboard_test.py"],
    deps = [
        ":dashboard_lib",
        ":metrics_lib",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pydantic",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "signal_cache_test",
    srcs = ["signal_cache_test.py"],
    deps = [
        ":signal_cache_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "batch_processor_test",
    srcs = ["batch_processor_test.py"],
    deps = [
        ":batch_processor_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "retention_test",
    srcs = ["retention_test.py"],
    deps = [
        ":retention_lib",
        "//third_party/python:pytest",
    ],
)
