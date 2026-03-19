load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "provider_lib",
    srcs = ["provider.py"],
    visibility = ["//visibility:public"],
)

py_library(
    name = "crypto_provider_lib",
    srcs = ["crypto_provider.py"],
    visibility = ["//visibility:public"],
    deps = [
        ":provider_lib",
        "//services/candle_ingestor:ccxt_client_lib",
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "stock_provider_lib",
    srcs = ["stock_provider.py"],
    visibility = ["//visibility:public"],
    deps = [
        ":provider_lib",
        "//third_party/python:absl_py",
        "//third_party/python:requests",
        "//third_party/python:tenacity",
    ],
)

py_library(
    name = "forex_provider_lib",
    srcs = ["forex_provider.py"],
    visibility = ["//visibility:public"],
    deps = [
        ":provider_lib",
        "//third_party/python:absl_py",
        "//third_party/python:requests",
        "//third_party/python:tenacity",
    ],
)

py_library(
    name = "registry_lib",
    srcs = ["registry.py"],
    visibility = ["//visibility:public"],
    deps = [
        ":provider_lib",
        "//third_party/python:absl_py",
    ],
)

py_test(
    name = "provider_test",
    srcs = ["provider_test.py"],
    deps = [
        ":provider_lib",
    ],
)

py_test(
    name = "crypto_provider_test",
    srcs = ["crypto_provider_test.py"],
    deps = [
        ":crypto_provider_lib",
        ":provider_lib",
        "//services/candle_ingestor:ccxt_client_lib",
        "//third_party/python:ccxt",
    ],
)

py_test(
    name = "stock_provider_test",
    srcs = ["stock_provider_test.py"],
    deps = [
        ":provider_lib",
        ":stock_provider_lib",
        "//third_party/python:requests",
    ],
)

py_test(
    name = "forex_provider_test",
    srcs = ["forex_provider_test.py"],
    deps = [
        ":forex_provider_lib",
        ":provider_lib",
        "//third_party/python:requests",
    ],
)

py_library(
    name = "commodities_provider_lib",
    srcs = ["commodities_provider.py"],
    visibility = ["//visibility:public"],
    deps = [
        ":provider_lib",
        "//third_party/python:absl_py",
        "//third_party/python:requests",
        "//third_party/python:tenacity",
    ],
)

py_test(
    name = "registry_test",
    srcs = ["registry_test.py"],
    deps = [
        ":provider_lib",
        ":registry_lib",
    ],
)

py_test(
    name = "commodities_provider_test",
    srcs = ["commodities_provider_test.py"],
    deps = [
        ":commodities_provider_lib",
        ":provider_lib",
        "//third_party/python:requests",
    ],
)
