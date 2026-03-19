load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "plans_lib",
    srcs = [
        "__init__.py",
        "plans.py",
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
        ":plans_lib",
        "//services/rest_api_shared:health",
        "//services/rest_api_shared:responses",
        "//services/shared:auth",
        "//third_party/python:asyncpg",
        "//third_party/python:fastapi",
        "//third_party/python:pydantic",
        "//third_party/python:stripe",
    ],
)

py_library(
    name = "gating_lib",
    srcs = [
        "__init__.py",
        "gating.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        ":plans_lib",
        "//third_party/python:asyncpg",
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
        ":plans_lib",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "gating_test",
    srcs = ["gating_test.py"],
    deps = [
        ":gating_lib",
        ":plans_lib",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
    ],
)

py_test(
    name = "plans_test",
    srcs = ["plans_test.py"],
    deps = [
        ":plans_lib",
        "//third_party/python:pytest",
    ],
)
