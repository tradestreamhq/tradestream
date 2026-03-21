load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "auth_service_lib",
    srcs = [
        "__init__.py",
        "auth_service.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/python:bcrypt",
        "//third_party/python:pyjwt",
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
        ":auth_service_lib",
        "//services/rest_api_shared:health",
        "//services/rest_api_shared:responses",
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
    name = "auth_service_test",
    srcs = ["auth_service_test.py"],
    deps = [
        ":auth_service_lib",
        "//third_party/python:pyjwt",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "app_test",
    srcs = ["app_test.py"],
    deps = [
        ":app_lib",
        ":auth_service_lib",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
    ],
)
