def define_jdk_toolchains():
    """Registers the JDK toolchains defined in //platforms:BUILD."""
    native.register_toolchains(
        "//platforms:jdk_toolchain_linux_amd64",
        "//platforms:jdk_toolchain_linux_arm64",
    )
