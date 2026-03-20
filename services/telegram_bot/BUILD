load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "bot_lib",
    srcs = [
        "__init__.py",
        "bot.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/python:requests",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":bot_lib",
        "//third_party/python:asyncpg",
    ],
)

py_test(
    name = "bot_test",
    srcs = ["bot_test.py"],
    deps = [
        ":bot_lib",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
        "//third_party/python:requests",
    ],
)
