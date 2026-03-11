# --- OCI Image Rules ---
load("@rules_python//python:defs.bzl", "py_binary", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "strategy_time_filter_lib",
    srcs = ["main.py"],
    deps = [
        "//services/shared:config",
        "//third_party/python:absl_py",
        "//third_party/python:asyncpg",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":strategy_time_filter_lib",
    ],
)
