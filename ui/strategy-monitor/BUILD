load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("@aspect_bazel_lib//lib:tar.bzl", "tar", "mtree_mutate")
load("@rules_python//python:defs.bzl", "py_test", "py_binary")
load("@container_structure_test//:defs.bzl", "container_structure_test")

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
    visibility = ["//visibility:public"],
)

# Create a tar of the UI files
tar(
    name = "ui_tar",
    srcs = [":ui_files"],
    mtree = "auto",
    out = "strategy_monitor_ui.tar",
)

# Create a simple HTTP server script (for development/testing only)
py_binary(
    name = "http_server",
    srcs = ["http_server.py"],
    data = [":ui_files"],
    deps = [],
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

# Static web server for the Strategy Monitor UI using nginx
oci_image(
    name = "strategy_monitor_ui",
    base = "@nginx_alpine",
    entrypoint = ["/usr/sbin/nginx"],
    tars = [":ui_tar"],
    user = "nginx",
    workdir = "/usr/share/nginx/html",
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

# Container structure test
filegroup(
    name = "container_structure_test_files",
    srcs = ["container-structure-test.yaml"],
)

container_structure_test(
    name = "container_test",
    image = ":strategy_monitor_ui",
    configs = [":container_structure_test_files"],
) 