load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push", "oci_load")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "postgres_client_lib",
    srcs = ["postgres_client.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:asyncpg",
        "//third_party/python:tenacity",
    ],
)

py_library(
    name = "kafka_consumer_lib",
    srcs = ["kafka_consumer.py"],
    deps = [
        "//protos:discovery_py_proto",
        "//protos:strategies_py_proto",
        "//third_party/python:absl_py",
        "//third_party/python:kafka_python",
        "//third_party/python:protobuf",
        "//third_party/python:tenacity",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":kafka_consumer_lib",
        ":postgres_client_lib",
        "//third_party/python:absl_py",
    ],
)

py_binary(
    name = "strategy_inspector",
    srcs = ["strategy_inspector.py"],
    deps = [
        "//protos:strategies_py_proto",
        "//third_party/python:asyncpg",
        "//third_party/python:protobuf",
    ],
)

# --- Test Targets ---
py_test(
    name = "postgres_client_test",
    srcs = ["postgres_client_test.py"],
    deps = [
        ":postgres_client_lib",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
    ],
)

py_test(
    name = "kafka_consumer_test",
    srcs = ["kafka_consumer_test.py"],
    deps = [
        ":kafka_consumer_lib",
        "//protos:discovery_py_proto",
        "//protos:strategies_py_proto",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
    ],
)

py_test(
    name = "main_test",
    srcs = ["main_test.py"],
    args = [
        "--kafka_bootstrap_servers=localhost:9092",
        "--kafka_topic=discovered-strategies",
        "--postgres_host=localhost",
        "--postgres_port=5432",
        "--postgres_database=tradestream",
        "--postgres_username=test_user",
        "--postgres_password=test_password",
    ],
    deps = [
        ":app",
        ":kafka_consumer_lib",
        ":postgres_client_lib",
        "//third_party/python:absl_py",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
    ],
)

py_test(
    name = "postgres_client_integration_test",
    srcs = ["postgres_client_integration_test.py"],
    deps = [
        ":postgres_client_lib",
        "//third_party/python:asyncpg",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
        "//third_party/python:testing_postgresql",
    ],
)

# --- OCI Image Rules ---
py_image_layer(
    name = "layers",
    binary = ":app",
)

oci_image(
    name = "image",
    base = "@python_3_13_slim",
    entrypoint = ["/services/strategy_consumer/app"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/strategy_consumer",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_strategy_consumer_image",
    image = ":images",
    repository = "tradestreamhq/strategy-consumer",
)

oci_load(
    name = "load_strategy_consumer_image",
    image = ":image",
    repo_tags = ["strategy-consumer:latest"],
)

filegroup(
    name = "strategy_consumer_tarball",
    srcs = [":load_strategy_consumer_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
