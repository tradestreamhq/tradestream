load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "config_lib",
    srcs = ["config.py"],
    deps = [
        "//services/shared:credentials",
    ],
)

py_library(
    name = "telegram_sender_lib",
    srcs = ["telegram_sender.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:requests",
    ],
)

py_library(
    name = "discord_sender_lib",
    srcs = ["discord_sender.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:requests",
    ],
)

py_library(
    name = "main_lib",
    srcs = ["main.py"],
    deps = [
        ":config_lib",
        ":discord_sender_lib",
        ":telegram_sender_lib",
        "//services/shared:structured_logger",
        "//third_party/python:absl_py",
        "//third_party/python:redis",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":main_lib",
    ],
)

py_test(
    name = "notification_service_test",
    srcs = ["notification_service_test.py"],
    deps = [
        ":config_lib",
        ":discord_sender_lib",
        ":main_lib",
        ":telegram_sender_lib",
        "//third_party/python:absl_py",
        "//third_party/python:pytest",
        "//third_party/python:redis",
        "//third_party/python:requests",
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
    entrypoint = ["/services/notification_service/app"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/notification_service",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_notification_service_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/notification-service",
)

oci_load(
    name = "load_notification_service_image",
    image = ":image",
    repo_tags = ["notification-service:latest"],
)

filegroup(
    name = "notification_service_tarball",
    srcs = [":load_notification_service_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
