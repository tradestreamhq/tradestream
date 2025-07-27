load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@rules_python//python:defs.bzl", "py_test")

# Package the UI files
filegroup(
    name = "ui_files",
    srcs = glob([
        "*.html",
        "*.js",
        "*.css",
        "*.md",
        "*.sh",
    ]),
)

# Create a tar of the UI files
tar(
    name = "ui_tar",
    srcs = [":ui_files"],
    out = "strategy_monitor_ui.tar",
)

# UI tests
py_test(
    name = "strategy_monitor_ui_test",
    srcs = ["ui_test.py"],
    main = "ui_test.py",
    data = [":ui_files"],
    deps = [],
    python_version = "PY3",
    size = "medium",
    timeout = "short",
)

# Static web server for the Strategy Monitor UI
oci_image(
    name = "strategy_monitor_ui",
    base = "@python_3_13_slim",
    entrypoint = [
        "/usr/bin/python3",
        "-m",
        "http.server",
        "8080",
        "--directory",
        "/app",
    ],
    tars = [":ui_tar"],
    user = "nobody",
    workdir = "/app",
)

# OCI image index for multi-platform support
oci_image_index(
    name = "strategy_monitor_ui_images",
    images = [
        ":strategy_monitor_ui",
    ],
)

# Push target for the UI image
oci_push(
    name = "push_strategy_monitor_ui_image",
    image = ":strategy_monitor_ui_images",
    repository = "tradestreamhq/strategy-monitor-ui",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":strategy_monitor_ui",
    tags = ["requires-docker"],
) 