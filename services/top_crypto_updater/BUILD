load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "redis_client_lib",
    srcs = ["redis_client.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:redis",
        "//third_party/python:tenacity",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":redis_client_lib",
        "//shared/cryptoclient:cmc_client_lib",
        "//third_party/python:absl_py",
        "//third_party/python:redis",
    ],
)

# --- Test Targets ---
py_test(
    name = "redis_client_test",
    srcs = ["redis_client_test.py"],
    deps = [
        ":redis_client_lib",
        "//third_party/python:absl_py",
        "//third_party/python:redis",
    ],
)

py_test(
    name = "main_test",
    srcs = ["main_test.py"],
    args = [
        "--cmc_api_key=dummy_cmc_key_for_test",
        "--redis_host=mockredis",
    ],
    deps = [
        ":app",
        ":redis_client_lib",
        "//shared/cryptoclient:cmc_client_lib",
        "//third_party/python:absl_py",
        "//third_party/python:redis",
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
    entrypoint = ["/services/top_crypto_updater/app"],
    tars = [":layers"],
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_top_crypto_updater_image",
    image = ":images",
    repository = "tradestreamhq/top-crypto-updater",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
