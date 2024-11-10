load("@bazel_skylib//rules:native_binary.bzl", "native_binary")
load("@rules_java//java:defs.bzl", "java_runtime", "java_toolchain")

package(default_visibility = ["//:__subpackages__"])

platform(
    name = "linux_arm64",
    constraint_values = [
        "@platforms//os:linux",
        "@platforms//cpu:arm64",
    ],
)

platform(
    name = "linux_amd64",
    constraint_values = [
        "@platforms//os:linux",
        "@platforms//cpu:x86_64",
    ],
)

config_setting(
    name = "platform_darwin_arm64",
    constraint_values = [
        "@platforms//os:macos",
        "@platforms//cpu:arm64",
    ],
)

config_setting(
    name = "platform_darwin_amd64",
    constraint_values = [
        "@platforms//os:macos",
        "@platforms//cpu:x86_64",
    ],
)

config_setting(
    name = "platform_linux_amd64",
    constraint_values = [
        "@platforms//os:linux",
        "@platforms//cpu:x86_64",
    ],
)

java_runtime(
    name = "jdk_linux_amd64",
    srcs = ["@rules_java//:jdk_linux_amd64"],
    java_home = "@rules_java//:jdk_linux_amd64",
    visibility = ["//visibility:public"],
)

java_toolchain(
    name = "jdk_toolchain_linux_amd64",
    source_version = "11",
    target_version = "11",
    java_runtime = ":jdk_linux_amd64",
    visibility = ["//visibility:public"],
)

java_runtime(
    name = "jdk_linux_arm64",
    srcs = ["@rules_java//:jdk_linux_arm64"],
    java_home = "@rules_java//:jdk_linux_arm64",
    visibility = ["//visibility:public"],
)

java_toolchain(
    name = "jdk_toolchain_linux_arm64",
    source_version = "11",
    target_version = "11",
    java_runtime = ":jdk_linux_arm64",
    visibility = ["//visibility:public"],
)
