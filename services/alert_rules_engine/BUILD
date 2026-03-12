load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "config_lib",
    srcs = ["config.py"],
)

py_library(
    name = "models_lib",
    srcs = ["models.py"],
)

py_library(
    name = "conditions_lib",
    srcs = ["conditions.py"],
    deps = [
        ":models_lib",
    ],
)

py_library(
    name = "rule_store_lib",
    srcs = ["rule_store.py"],
    deps = [
        ":models_lib",
        "//third_party/python:redis",
    ],
)

py_library(
    name = "actions_lib",
    srcs = ["actions.py"],
    deps = [
        "//services/shared:structured_logger",
        "//third_party/python:requests",
    ],
)

py_library(
    name = "engine_lib",
    srcs = ["engine.py"],
    deps = [
        ":actions_lib",
        ":conditions_lib",
        ":models_lib",
        ":rule_store_lib",
        "//services/shared:structured_logger",
        "//third_party/python:requests",
    ],
)

py_library(
    name = "main_lib",
    srcs = ["main.py"],
    deps = [
        ":config_lib",
        ":engine_lib",
        ":models_lib",
        ":rule_store_lib",
        "//services/shared:structured_logger",
        "//third_party/python:absl_py",
        "//third_party/python:flask",
        "//third_party/python:redis",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":main_lib",
    ],
)

py_test(
    name = "alert_rules_engine_test",
    srcs = ["alert_rules_engine_test.py"],
    deps = [
        ":actions_lib",
        ":conditions_lib",
        ":config_lib",
        ":engine_lib",
        ":main_lib",
        ":models_lib",
        ":rule_store_lib",
        "//third_party/python:flask",
        "//third_party/python:pytest",
        "//third_party/python:redis",
        "//third_party/python:requests",
    ],
)
