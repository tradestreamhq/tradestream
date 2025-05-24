load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "cmc_client_lib",
    srcs = ["cmc_client.py"],
    deps = [
        "//third_party:absl_py",
        "//third_party:requests",
        "//third_party:tenacity",
    ],
)

py_test(
    name = "cmc_client_test",
    srcs = ["cmc_client_test.py"],
    deps = [
        ":cmc_client_lib",
        "//third_party:requests",
    ],
)
