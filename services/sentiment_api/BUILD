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
    name = "feed_processor_lib",
    srcs = [
        "__init__.py",
        "feed_processor.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        ":analyzer_lib",
        ":models_lib",
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
        ":feed_processor_lib",
        "//services/rest_api_shared:health",
        "//services/rest_api_shared:responses",
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
        "//third_party/python:uvicorn",
    ],
)

py_test(
    name = "analyzer_test",
    srcs = ["analyzer_test.py"],
    deps = [
        ":analyzer_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "feed_processor_test",
    srcs = ["feed_processor_test.py"],
    deps = [
        ":feed_processor_lib",
        ":models_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "app_test",
    srcs = ["app_test.py"],
    deps = [
        ":app_lib",
        ":feed_processor_lib",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
    ],
)
