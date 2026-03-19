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
    name = "pine_script_lib",
    srcs = [
        "__init__.py",
        "pine_script.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        ":models_lib",
    ],
)

py_library(
    name = "alert_publisher_lib",
    srcs = [
        "__init__.py",
        "alert_publisher.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/python:requests",
        "//third_party/python:tenacity",
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
        ":alert_publisher_lib",
        ":models_lib",
        ":pine_script_lib",
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
    name = "models_test",
    srcs = ["models_test.py"],
    deps = [
        ":models_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "pine_script_test",
    srcs = ["pine_script_test.py"],
    deps = [
        ":models_lib",
        ":pine_script_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "alert_publisher_test",
    srcs = ["alert_publisher_test.py"],
    deps = [
        ":alert_publisher_lib",
        "//third_party/python:pytest",
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
