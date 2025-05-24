load("@rules_python//python:defs.bzl", "py_binary", "py_library", "py_test")

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
        "//third_party/python:absl_py",
        "//third_party/python:influxdb_client",
        "//third_party/python:protobuf",
        "//third_party/python:tenacity",
    ],
)

py_library(
    name = "candle_processor_lib",
    srcs = ["candle_processor.py"],
    deps = [
        "//protos:backtesting_py_proto",
        "//protos:marketdata_py_proto",
        "//protos:strategies_py_proto",
        "//third_party/python:absl_py",
        "//third_party/python:protobuf",
    ],
)

py_library(
    name = "kafka_publisher_lib",
    srcs = ["kafka_publisher.py"],
    deps = [
        "//protos:backtesting_py_proto",
        "//third_party/python:absl_py",
        "//third_party/python:kafka_python",
        "//third_party/python:tenacity",
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
        "//third_party/python:absl_py",
        "//third_party/protobuf",
    ],
)

# Test dependencies
py_library(
    name = "test_utils_lib",
    srcs = ["test_utils.py"],
    deps = [
        "//protos:backtesting_py_proto",
        "//protos:marketdata_py_proto",
        "//protos:strategies_py_proto",
        "//third_party/python:protobuf",
    ],
    testonly = 1,
)

# Unit Tests
py_test(
    name = "config_test",
    srcs = ["config_test.py"],
    deps = [
        ":config_lib",
        "//protos:strategies_py_proto",
    ],
    python_version = "PY3",
)

py_test(
    name = "influx_poller_test",
    srcs = ["influx_poller_test.py"],
    deps = [
        ":influx_poller_lib",
        ":test_utils_lib",
        "//protos:marketdata_py_proto",
        "//third_party/python:influxdb_client",
        "//third_party/python:protobuf",
    ],
    python_version = "PY3",
)

py_test(
    name = "candle_processor_test",
    srcs = ["candle_processor_test.py"],
    deps = [
        ":candle_processor_lib",
        ":test_utils_lib",
        "//protos:backtesting_py_proto",
        "//protos:marketdata_py_proto",
        "//protos:strategies_py_proto",
        "//third_party/python:protobuf",
    ],
    python_version = "PY3",
)

py_test(
    name = "kafka_publisher_test",
    srcs = ["kafka_publisher_test.py"],
    deps = [
        ":kafka_publisher_lib",
        ":test_utils_lib",
        "//protos:backtesting_py_proto",
        "//third_party/python:kafka_python",
    ],
    python_version = "PY3",
)

py_test(
    name = "main_test",
    srcs = ["main_test.py"],
    deps = [
        ":app",
        ":candle_processor_lib",
        ":config_lib",
        ":influx_poller_lib",
        ":kafka_publisher_lib",
        ":test_utils_lib",
        "//shared/cryptoclient:cmc_client_lib",
        "//third_party/python:absl_py",
    ],
    python_version = "PY3",
)

# Integration Tests
py_test(
    name = "integration_test",
    srcs = ["integration_test.py"],
    deps = [
        ":candle_processor_lib",
        ":influx_poller_lib",
        ":kafka_publisher_lib",
        ":test_utils_lib",
        "//protos:backtesting_py_proto",
        "//protos:marketdata_py_proto",
        "//third_party/python:influxdb_client",
        "//third_party/python:kafka_python",
    ],
    python_version = "PY3",
    size = "medium",
)

# Test Suite Target
test_suite(
    name = "all_tests",
    tests = [
        ":config_test",
        ":influx_poller_test", 
        ":candle_processor_test",
        ":kafka_publisher_test",
        ":main_test",
        ":integration_test",
    ],
)
