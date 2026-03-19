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
    name = "slack_sender_lib",
    srcs = ["slack_sender.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:requests",
    ],
)

py_library(
    name = "webhook_sender_lib",
    srcs = ["webhook_sender.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:requests",
        "//third_party/python:tenacity",
    ],
)

py_library(
    name = "email_sender_lib",
    srcs = ["email_sender.py"],
    deps = [
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "notification_history_lib",
    srcs = ["notification_history.py"],
    deps = [
        "//third_party/python:redis",
    ],
)

py_library(
    name = "channel_lib",
    srcs = ["channel.py"],
)

py_library(
    name = "sms_sender_lib",
    srcs = ["sms_sender.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:requests",
    ],
)

py_library(
    name = "deduplicator_lib",
    srcs = ["deduplicator.py"],
)

py_library(
    name = "rate_limiter_lib",
    srcs = ["rate_limiter.py"],
)

py_library(
    name = "user_preferences_lib",
    srcs = ["user_preferences.py"],
)

py_library(
    name = "delivery_router_lib",
    srcs = ["delivery_router.py"],
    deps = [
        ":deduplicator_lib",
        ":rate_limiter_lib",
        ":user_preferences_lib",
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "delivery_tracker_lib",
    srcs = ["delivery_tracker.py"],
)

py_library(
    name = "main_lib",
    srcs = ["main.py"],
    deps = [
        ":config_lib",
        ":discord_sender_lib",
        ":email_sender_lib",
        ":notification_history_lib",
        ":slack_sender_lib",
        ":sms_sender_lib",
        ":telegram_sender_lib",
        ":webhook_sender_lib",
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
        ":email_sender_lib",
        ":main_lib",
        ":notification_history_lib",
        ":slack_sender_lib",
        ":sms_sender_lib",
        ":telegram_sender_lib",
        ":webhook_sender_lib",
        "//third_party/python:absl_py",
        "//third_party/python:pytest",
        "//third_party/python:redis",
        "//third_party/python:requests",
        "//third_party/python:tenacity",
    ],
)

py_test(
    name = "multi_channel_test",
    srcs = ["multi_channel_test.py"],
    deps = [
        ":channel_lib",
        ":deduplicator_lib",
        ":delivery_router_lib",
        ":delivery_tracker_lib",
        ":rate_limiter_lib",
        ":sms_sender_lib",
        ":user_preferences_lib",
        "//third_party/python:absl_py",
        "//third_party/python:pytest",
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
