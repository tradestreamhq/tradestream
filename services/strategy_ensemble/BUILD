load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "main_lib",
    srcs = ["main.py"],
    deps = [
        "//services/shared:credentials",
        "//third_party/python:absl_py",
        "//third_party/python:asyncpg",
    ],
)

py_test(
    name = "strategy_ensemble_test",
    srcs = ["main_test.py"],
    main = "main_test.py",
    deps = [
        ":main_lib",
        "//third_party/python:absl_py",
        "//third_party/python:pytest",
    ],
)
