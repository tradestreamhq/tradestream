load("@bazel_skylib//rules:native_binary.bzl", "native_binary")

package(default_visibility = ["//:__subpackages__"])

native_binary(
    name = "docker_cli",
    src = select({
        "@bazel_tools//src/conditions:linux_x86_64": "@docker_cli_linux_amd64//:docker",
        "@bazel_tools//src/conditions:linux_aarch64": "@docker_cli_linux_arm64//:docker",
        "@bazel_tools//src/conditions:darwin_arm64": "@docker_cli_darwin_arm64//:docker",
        "@bazel_tools//src/conditions:darwin_x86_64": "@docker_cli_darwin_amd64//:docker",
    }),
    out = "docker",
)

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
