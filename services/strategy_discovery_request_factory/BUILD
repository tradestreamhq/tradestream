load("@rules_python//python:defs.bzl", "py_binary", "py_library", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "config_lib",
    srcs = ["config.py"],
    deps = [],
)

py_library(
    name = "strategy_discovery_processor_lib",
    srcs = ["strategy_discovery_processor.py"],
    deps = [
        "//protos:discovery_py_proto",
        "//protos:strategies_py_proto",
        "//third_party/python:absl_py",
        "//third_party/python:protobuf",
    ],
)

py_library(
    name = "kafka_publisher_lib",
    srcs = ["kafka_publisher.py"],
    deps = [
        "//protos:discovery_py_proto",
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
        ":config_lib",
        ":kafka_publisher_lib",
        ":strategy_discovery_processor_lib",
        "//shared/persistence:influxdb_last_processed_tracker_lib",
        "//third_party/python:absl_py",
        "//third_party/python:protobuf",
    ],
)

# Unit Tests
py_test(
    name = "config_test",
    srcs = ["config_test.py"],
    deps = [
        ":config_lib",
    ],
)

py_test(
    name = "strategy_discovery_processor_test",
    srcs = ["strategy_discovery_processor_test.py"],
    deps = [
        ":strategy_discovery_processor_lib",
        "//protos:discovery_py_proto",
        "//protos:strategies_py_proto",
        "//third_party/python:protobuf",
    ],
)

py_test(
    name = "kafka_publisher_test",
    srcs = ["kafka_publisher_test.py"],
    deps = [
        ":kafka_publisher_lib",
        "//protos:discovery_py_proto",
        "//third_party/python:kafka_python",
        "//third_party/python:protobuf",
    ],
)

py_test(
    name = "main_test",
    srcs = ["main_test.py"],
    args = [
        "--influxdb_token=dummy_token_for_test",
        "--influxdb_org=dummy_org_for_test",
        "--currency_pairs=BTC/USD,ETH/USD",
        "--tracker_service_name=test_strategy_discovery",
        "--global_status_tracker_service_name=test_global_candle_status",
    ],
    deps = [
        ":app",
        ":config_lib",
        ":kafka_publisher_lib",
        ":strategy_discovery_processor_lib",
        "//shared/persistence:influxdb_last_processed_tracker_lib",
        "//third_party/python:absl_py",
    ],
)

# Integration Tests
py_test(
    name = "integration_test",
    srcs = ["integration_test.py"],
    deps = [
        ":kafka_publisher_lib",
        ":strategy_discovery_processor_lib",
        "//protos:discovery_py_proto",
        "//shared/persistence:influxdb_last_processed_tracker_lib",
        "//third_party/python:kafka_python",
        "//third_party/python:protobuf",
    ],
)
