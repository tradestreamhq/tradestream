load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "channels_base",
    srcs = ["channels/base.py"],
)

py_library(
    name = "telegram_channel",
    srcs = ["channels/telegram.py"],
    deps = [
        ":channels_base",
        "//third_party/python:absl_py",
        "//third_party/python:requests",
    ],
)

py_library(
    name = "discord_channel",
    srcs = ["channels/discord.py"],
    deps = [
        ":channels_base",
        "//third_party/python:absl_py",
        "//third_party/python:requests",
    ],
)

py_library(
    name = "slack_channel",
    srcs = ["channels/slack.py"],
    deps = [
        ":channels_base",
        "//third_party/python:absl_py",
        "//third_party/python:requests",
    ],
)

py_library(
    name = "email_channel",
    srcs = ["channels/email.py"],
    deps = [
        ":channels_base",
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "sms_channel",
    srcs = ["channels/sms.py"],
    deps = [
        ":channels_base",
        "//third_party/python:absl_py",
        "//third_party/python:requests",
    ],
)

py_library(
    name = "webhook_channel",
    srcs = ["channels/webhook.py"],
    deps = [
        ":channels_base",
        "//third_party/python:absl_py",
        "//third_party/python:requests",
    ],
)

py_library(
    name = "channels",
    srcs = ["channels/__init__.py"],
    deps = [
        ":channels_base",
        ":discord_channel",
        ":email_channel",
        ":slack_channel",
        ":sms_channel",
        ":telegram_channel",
        ":webhook_channel",
    ],
)

py_library(
    name = "deduplication",
    srcs = ["deduplication.py"],
)

py_library(
    name = "rate_limiter",
    srcs = ["rate_limiter.py"],
)

py_library(
    name = "preferences",
    srcs = ["preferences.py"],
)

py_library(
    name = "tracker",
    srcs = ["tracker.py"],
)

py_library(
    name = "router",
    srcs = ["router.py"],
    deps = [
        ":channels_base",
        ":deduplication",
        ":preferences",
        ":rate_limiter",
        ":tracker",
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "main_lib",
    srcs = ["main.py"],
    deps = [
        ":channels",
        ":deduplication",
        ":preferences",
        ":rate_limiter",
        ":router",
        ":tracker",
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
    name = "delivery_test",
    srcs = ["delivery_test.py"],
    deps = [
        ":channels",
        ":channels_base",
        ":deduplication",
        ":preferences",
        ":rate_limiter",
        ":router",
        ":tracker",
        "//third_party/python:absl_py",
        "//third_party/python:pytest",
        "//third_party/python:requests",
    ],
)
