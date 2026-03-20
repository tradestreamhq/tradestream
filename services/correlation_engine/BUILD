load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "engine_lib",
    srcs = [
        "__init__.py",
        "engine.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/python:numpy",
        "//third_party/python:pandas",
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
        ":engine_lib",
        "//services/rest_api_shared:health",
        "//services/rest_api_shared:responses",
        "//services/shared:auth",
        "//third_party/python:fastapi",
        "//third_party/python:numpy",
        "//third_party/python:pandas",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":app_lib",
        "//services/market_mcp:influxdb_client_lib",
        "//services/market_mcp:redis_client_lib",
        "//third_party/python:uvicorn",
    ],
)

py_test(
    name = "engine_test",
    srcs = ["engine_test.py"],
    deps = [
        ":engine_lib",
        "//third_party/python:numpy",
        "//third_party/python:pandas",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "app_test",
    srcs = ["app_test.py"],
    deps = [
        ":app_lib",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:numpy",
        "//third_party/python:pytest",
    ],
)
