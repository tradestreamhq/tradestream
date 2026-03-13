load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "schema_lib",
    srcs = [
        "__init__.py",
        "schema.py",
    ],
    visibility = ["//visibility:public"],
)

py_library(
    name = "config_service_lib",
    srcs = [
        "__init__.py",
        "config_service.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        ":schema_lib",
        "//third_party/python:pyyaml",
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
        ":config_service_lib",
        "//services/rest_api_shared:health",
        "//services/rest_api_shared:responses",
        "//services/shared:auth",
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
        ":config_service_lib",
        "//third_party/python:uvicorn",
    ],
)

py_test(
    name = "app_test",
    srcs = ["app_test.py"],
    deps = [
        ":app_lib",
        ":config_service_lib",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
        "//third_party/python:pyyaml",
    ],
)
