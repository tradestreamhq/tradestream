load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "cmc_client_lib",
    srcs = ["cmc_client.py"],
    visibility = [
        "//services/candle_ingestor:__pkg__",
        "//services/top_crypto_updater:__pkg__",
    ],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:requests",
        "//third_party/python:tenacity",
    ],
)

py_test(
    name = "cmc_client_test",
    srcs = ["cmc_client_test.py"],
    deps = [
        ":cmc_client_lib",
        "//third_party/python:requests",
    ],
)

py_library(
    name = "redis_crypto_client_lib",
    srcs = ["redis_crypto_client.py"],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:redis",
        "//third_party/python:tenacity",
    ],
)

py_test(
    name = "redis_crypto_client_test",
    srcs = ["redis_crypto_client_test.py"],
    deps = [
        ":redis_crypto_client_lib",
        "//third_party/python:absl_py",
        "//third_party/python:redis",
    ],
)
