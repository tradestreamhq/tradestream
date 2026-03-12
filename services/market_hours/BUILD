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
    name = "calendar_lib",
    srcs = [
        "__init__.py",
        "calendar.py",
    ],
    deps = [
        ":models_lib",
    ],
)

py_library(
    name = "schedule_lib",
    srcs = [
        "__init__.py",
        "schedule.py",
    ],
    deps = [
        ":calendar_lib",
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
        ":calendar_lib",
        ":models_lib",
        ":schedule_lib",
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
    name = "market_hours_test",
    srcs = ["app_test.py"],
    main = "app_test.py",
    deps = [
        ":app_lib",
        ":calendar_lib",
        ":models_lib",
        ":schedule_lib",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
    ],
)
