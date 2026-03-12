load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "generate_lib",
    srcs = ["generate.py"],
    deps = [
        "//third_party/python:pyyaml",
    ],
)

py_binary(
    name = "generate",
    srcs = [
        "__main__.py",
        "generate.py",
    ],
    main = "__main__.py",
    deps = [
        "//third_party/python:pyyaml",
    ],
)

py_test(
    name = "generate_test",
    srcs = ["generate_test.py"],
    deps = [
        ":generate_lib",
        "//third_party/python:pyyaml",
    ],
)
