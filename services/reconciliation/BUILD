load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "models_lib",
    srcs = [
        "__init__.py",
        "models.py",
    ],
    visibility = ["//visibility:public"],
)

py_library(
    name = "exchange_client_lib",
    srcs = [
        "__init__.py",
        "exchange_client.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        ":models_lib",
        "//third_party/python:ccxt",
    ],
)

py_library(
    name = "reconciler_lib",
    srcs = [
        "__init__.py",
        "reconciler.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        ":exchange_client_lib",
        ":models_lib",
        "//third_party/python:asyncpg",
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
        ":exchange_client_lib",
        ":reconciler_lib",
        "//services/rest_api_shared:health",
        "//services/rest_api_shared:responses",
        "//services/shared:auth",
        "//third_party/python:asyncpg",
        "//third_party/python:fastapi",
        "//third_party/python:pydantic",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":app_lib",
        ":exchange_client_lib",
        "//third_party/python:asyncpg",
        "//third_party/python:uvicorn",
    ],
)

py_test(
    name = "reconciler_test",
    srcs = ["reconciler_test.py"],
    deps = [
        ":models_lib",
        ":reconciler_lib",
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
        "//third_party/python:pytest",
    ],
)
