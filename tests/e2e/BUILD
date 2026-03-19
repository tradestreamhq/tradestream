load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "e2e_conftest",
    srcs = [
        "__init__.py",
        "conftest.py",
    ],
    deps = [
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_signal_pipeline_e2e",
    srcs = ["test_signal_pipeline_e2e.py"],
    deps = [
        ":e2e_conftest",
        "//services/shared:alerting",
        "//services/shared:circuit_breaker",
        "//services/shared:dead_letter_queue",
        "//services/shared:pipeline_metrics",
        "//services/signal_api:delivery_lib",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
    ],
)

py_test(
    name = "test_billing_flow_e2e",
    srcs = ["test_billing_flow_e2e.py"],
    deps = [
        ":e2e_conftest",
        "//services/billing:gating_lib",
        "//services/billing:plans_lib",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
    ],
)

py_test(
    name = "test_marketplace_flow_e2e",
    srcs = ["test_marketplace_flow_e2e.py"],
    deps = [
        ":e2e_conftest",
        "//services/strategy_marketplace_api:app_lib",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_multi_channel_delivery_e2e",
    srcs = ["test_multi_channel_delivery_e2e.py"],
    deps = [
        ":e2e_conftest",
        "//services/delivery:channels_base",
        "//services/delivery:deduplication",
        "//services/delivery:preferences",
        "//services/delivery:rate_limiter",
        "//services/delivery:router",
        "//services/delivery:tracker",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_learning_engine_e2e",
    srcs = ["test_learning_engine_e2e.py"],
    deps = [
        ":e2e_conftest",
        "//services/learning_engine:regime_detector_lib",
        "//services/learning_engine:weight_optimizer_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_agent_orchestration_e2e",
    srcs = ["test_agent_orchestration_e2e.py"],
    deps = [
        ":e2e_conftest",
        "//services/agent_orchestration:config_lib",
        "//services/agent_orchestration:orchestration_loop_lib",
        "//services/agent_orchestration:resilience_lib",
        "//services/agent_orchestration:state_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_performance_tracking_e2e",
    srcs = ["test_performance_tracking_e2e.py"],
    deps = [
        ":e2e_conftest",
        "//services/portfolio_state:portfolio_state_lib",
        "//services/shared:pipeline_metrics",
        "//services/signal_quality:scorer_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_user_journey_e2e",
    srcs = ["test_user_journey_e2e.py"],
    deps = [
        ":e2e_conftest",
        "//services/billing:gating_lib",
        "//services/billing:plans_lib",
        "//services/shared:pipeline_metrics",
        "//services/signal_quality:scorer_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_data_generators",
    srcs = ["test_data_generators.py"],
    deps = [
        ":e2e_conftest",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
    ],
)
