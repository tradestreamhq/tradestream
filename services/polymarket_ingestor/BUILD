load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "polymarket_api_client_lib",
    srcs = ["polymarket_api_client.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:requests",
        "//third_party/python:tenacity",
    ],
)

py_library(
    name = "kafka_producer_lib",
    srcs = ["kafka_producer.py"],
    deps = [
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
        ":kafka_producer_lib",
        ":polymarket_api_client_lib",
        "//protos:polymarket_py_proto",
        "//third_party/python:absl_py",
        "//third_party/python:requests",
    ],
)

# --- Test Targets ---
py_test(
    name = "polymarket_api_client_test",
    srcs = ["polymarket_api_client_test.py"],
    deps = [
        ":polymarket_api_client_lib",
        "//third_party/python:requests",
    ],
)

py_test(
    name = "kafka_producer_test",
    srcs = ["kafka_producer_test.py"],
    deps = [
        ":kafka_producer_lib",
        "//third_party/python:kafka_python",
    ],
)

py_test(
    name = "main_test",
    srcs = ["main_test.py"],
    args = [
        "--run_mode=dry",
        "--polymarket_api_url=https://clob.polymarket.com",
    ],
    deps = [
        ":app",
        ":kafka_producer_lib",
        ":polymarket_api_client_lib",
        "//protos:polymarket_py_proto",
        "//third_party/python:absl_py",
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
    entrypoint = ["/services/polymarket_ingestor/app"],
    tars = [":layers"],
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_polymarket_ingestor_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/polymarket-ingestor",
)

oci_load(
    name = "load_polymarket_ingestor_image",
    image = ":image",
    repo_tags = ["polymarket-ingestor:latest"],
)

filegroup(
    name = "polymarket_ingestor_tarball",
    srcs = [":load_polymarket_ingestor_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
