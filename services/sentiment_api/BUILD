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
    name = "analyzer_lib",
    srcs = [
        "__init__.py",
        "analyzer.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        ":models_lib",
    ],
)

py_library(
    name = "data_provider_lib",
    srcs = [
        "__init__.py",
        "data_provider.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/python:ccxt",
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
        ":analyzer_lib",
        "//services/rest_api_shared:health",
        "//services/rest_api_shared:responses",
        "//services/shared:auth",
        "//third_party/python:fastapi",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":app_lib",
        ":data_provider_lib",
        "//third_party/python:uvicorn",
    ],
)

py_test(
    name = "analyzer_test",
    srcs = ["analyzer_test.py"],
    deps = [
        ":analyzer_lib",
        ":models_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "app_test",
    srcs = ["app_test.py"],
    deps = [
        ":analyzer_lib",
        ":app_lib",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
    ],
)
