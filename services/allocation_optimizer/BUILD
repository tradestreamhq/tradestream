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
    deps = [
        "//third_party/python:pydantic",
    ],
)

py_library(
    name = "covariance_lib",
    srcs = [
        "__init__.py",
        "covariance.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/python:numpy",
    ],
)

py_library(
    name = "optimizer_lib",
    srcs = [
        "__init__.py",
        "optimizer.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        ":covariance_lib",
        ":models_lib",
        "//third_party/python:numpy",
        "//third_party/python:scipy",
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
        ":models_lib",
        ":optimizer_lib",
        "//services/rest_api_shared:health",
        "//services/rest_api_shared:responses",
        "//third_party/python:fastapi",
        "//third_party/python:numpy",
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
    name = "app_test",
    srcs = ["app_test.py"],
    deps = [
        ":app_lib",
        ":covariance_lib",
        ":optimizer_lib",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:numpy",
        "//third_party/python:pytest",
    ],
)
