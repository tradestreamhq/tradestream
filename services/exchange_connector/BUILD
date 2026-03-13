load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "base",
    srcs = [
        "__init__.py",
        "base.py",
    ],
)

py_library(
    name = "mock_connector",
    srcs = [
        "__init__.py",
        "mock_connector.py",
    ],
    deps = [":base"],
)

py_library(
    name = "binance_connector",
    srcs = [
        "__init__.py",
        "binance_connector.py",
    ],
    deps = [
        ":base",
        "//third_party/python:absl_py",
        "//third_party/python:ccxt",
        "//third_party/python:tenacity",
    ],
)

py_library(
    name = "registry",
    srcs = [
        "__init__.py",
        "registry.py",
    ],
    deps = [":base"],
)

py_library(
    name = "app_lib",
    srcs = [
        "__init__.py",
        "app.py",
    ],
    deps = [
        ":base",
        ":registry",
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
        ":mock_connector",
        ":registry",
        "//third_party/python:absl_py",
        "//third_party/python:uvicorn",
    ],
)

py_test(
    name = "app_test",
    srcs = ["app_test.py"],
    deps = [
        ":app_lib",
        ":base",
        ":mock_connector",
        ":registry",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
    ],
)
