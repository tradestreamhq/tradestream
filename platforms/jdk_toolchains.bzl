load("@rules_java//java:defs.bzl", "java_runtime", "java_toolchain")

def define_jdk_toolchains():
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
        runtime = ":jdk_linux_amd64",
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
        runtime = ":jdk_linux_arm64",
    )

    native.register_toolchains(
        ":jdk_toolchain_linux_amd64",
        ":jdk_toolchain_linux_arm64",
    )
