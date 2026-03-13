load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "delivery_lib",
    srcs = [
        "__init__.py",
        "delivery.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/python:httpx",
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
        ":delivery_lib",
        "//services/rest_api_shared:health",
        "//services/rest_api_shared:pagination",
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
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "delivery_test",
    srcs = ["delivery_test.py"],
    deps = [
        ":delivery_lib",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
    ],
)
