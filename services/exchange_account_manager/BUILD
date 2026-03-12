load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "credential_store",
    srcs = [
        "__init__.py",
        "credential_store.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/python:cryptography",
    ],
)

py_library(
    name = "models_lib",
    srcs = [
        "__init__.py",
        "models.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/python:pydantic",
    ],
)

py_library(
    name = "exchange_client",
    srcs = [
        "__init__.py",
        "exchange_client.py",
    ],
    visibility = ["//visibility:public"],
)

py_library(
    name = "app_lib",
    srcs = [
        "__init__.py",
        "app.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        ":credential_store",
        ":exchange_client",
        ":models_lib",
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
        "//third_party/python:asyncpg",
        "//third_party/python:uvicorn",
    ],
)

py_test(
    name = "app_test",
    srcs = ["app_test.py"],
    deps = [
        ":app_lib",
        "//third_party/python:cryptography",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "credential_store_test",
    srcs = ["credential_store_test.py"],
    deps = [
        ":credential_store",
        "//third_party/python:cryptography",
        "//third_party/python:pytest",
    ],
)
