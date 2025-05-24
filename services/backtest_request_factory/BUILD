load("@rules_python//python:defs.bzl", "py_binary", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "config_lib",
    srcs = ["config.py"],
    deps = [
        "//protos:strategies_py_proto",
    ],
)

py_library(
    name = "influx_poller_lib",
    srcs = ["influx_poller.py"],
    deps = [
        "//protos:marketdata_py_proto",
        "//third_party:absl_py",
        "//third_party:influxdb_client",
        "//third_party:protobuf",
        "//third_party:tenacity",
    ],
)

py_library(
    name = "candle_processor_lib",
    srcs = ["candle_processor.py"],
    deps = [
        "//protos:backtesting_py_proto",
        "//protos:marketdata_py_proto",
        "//protos:strategies_py_proto",
        "@pypi//absl_py",
        "//third_party:absl_py",
        "//third_party:protobuf",
    ],
)

py_library(
    name = "kafka_publisher_lib",
    srcs = ["kafka_publisher.py"],
    deps = [
        "//protos:backtesting_py_proto",
        "@pypi//absl_py",
        "@pypi//kafka_python",
        "@pypi//tenacity",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":candle_processor_lib",
        ":config_lib",
        ":influx_poller_lib",
        ":kafka_publisher_lib",
        "//shared/cryptoclient:cmc_client_lib",
        "@pypi//absl_py",
        "@pypi//google-api-python-client", # For google.protobuf.any_pb2
    ],
)
