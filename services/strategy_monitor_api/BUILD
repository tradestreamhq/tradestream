load("@rules_python//python:defs.bzl", "py_binary", "py_library")

py_library(
    name = "strategy_monitor_api_lib",
    srcs = ["main.py"],
    deps = [
        "//third_party/py/flask",
        "//third_party/py/flask_cors", 
        "//third_party/py/asyncpg",
        "//third_party/py/absl",
    ],
)

py_binary(
    name = "strategy_monitor_api",
    srcs = ["main.py"],
    main = "main.py",
    deps = [":strategy_monitor_api_lib"],
)
