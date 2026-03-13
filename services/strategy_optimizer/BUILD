load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "grid_search_lib",
    srcs = [
        "__init__.py",
        "grid_search.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        "//services/backtesting:vectorbt_runner_lib",
    ],
)

py_library(
    name = "app_lib",
    srcs = [
        "__init__.py",
        "app.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        ":grid_search_lib",
        "//services/backtesting:vectorbt_runner_lib",
        "//services/rest_api_shared:health",
        "//services/rest_api_shared:responses",
        "//services/shared:auth",
        "//third_party/python:fastapi",
        "//third_party/python:numpy",
        "//third_party/python:pandas",
        "//third_party/python:pydantic",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":app_lib",
        "//third_party/python:uvicorn",
    ],
)

py_test(
    name = "test_grid_search",
    size = "medium",
    srcs = ["tests/test_grid_search.py"],
    deps = [
        ":grid_search_lib",
        "//services/backtesting:vectorbt_runner_lib",
        "//third_party/python:numpy",
        "//third_party/python:pandas",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_app",
    size = "small",
    srcs = ["tests/test_app.py"],
    deps = [
        ":app_lib",
        ":grid_search_lib",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
    ],
)
