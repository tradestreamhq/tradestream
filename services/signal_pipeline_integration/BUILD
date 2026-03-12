load("@rules_python//python:py_test.bzl", "py_test")

py_test(
    name = "signal_pipeline_integration_test",
    srcs = ["signal_pipeline_integration_test.py"],
    deps = [
        "//services/notification_service:main_lib",
        "//services/notification_service:notification_history_lib",
        "//services/signal_mcp:server_lib",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
    ],
)
