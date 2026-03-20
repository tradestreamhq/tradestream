load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "models_lib",
    srcs = [
        "__init__.py",
        "models.py",
    ],
)

py_library(
    name = "scoring_lib",
    srcs = [
        "__init__.py",
        "scoring.py",
    ],
    deps = [
        ":models_lib",
    ],
)

py_library(
    name = "aggregator_lib",
    srcs = [
        "__init__.py",
        "aggregator.py",
    ],
    deps = [
        ":models_lib",
        ":scoring_lib",
    ],
)

py_library(
    name = "lifecycle_lib",
    srcs = [
        "__init__.py",
        "lifecycle.py",
    ],
    deps = [
        ":models_lib",
    ],
)

py_library(
    name = "app_lib",
    srcs = [
        "__init__.py",
        "app.py",
    ],
    deps = [
        ":aggregator_lib",
        ":lifecycle_lib",
        ":models_lib",
        ":scoring_lib",
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
        "//third_party/python:uvicorn",
    ],
)

py_test(
    name = "scoring_test",
    srcs = ["scoring_test.py"],
    deps = [
        ":aggregator_lib",
        ":app_lib",
        ":lifecycle_lib",
        ":models_lib",
        ":scoring_lib",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
    ],
)
