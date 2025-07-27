load("@aspect_bazel_lib//lib:tar.bzl", "mtree_mutate", "tar")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("@rules_python//python:defs.bzl", "py_binary", "py_test")

# Package the UI files and nginx config
filegroup(
    name = "ui_files",
    srcs = glob([
        "*.html",
        "*.js",
        "*.css",
        "*.md",
        "*.sh",
        "*.conf",
    ]),
    visibility = ["//visibility:public"],
)

# Package the UI files and nginx config
tar(
    name = "ui_tar",
    srcs = [":ui_files"],
    out = "strategy_monitor_ui.tar",
    mtree = "auto",
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
    size = "medium",
    timeout = "short",
    srcs = ["ui_test.py"],
    data = [":ui_files"],
    main = "ui_test.py",
    python_version = "PY3",
    deps = [],
)

# Static web server for the Strategy Monitor UI using nginx
oci_image(
    name = "strategy_monitor_ui",
    base = "@nginx_alpine",
    entrypoint = ["/bin/sh"],
    cmd = ["-c", "cp /ui/strategy-monitor/nginx.conf /etc/nginx/nginx.conf && exec nginx -g 'daemon off;'"],
    tars = [":ui_tar"],
    user = "root",
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
    configs = [":container_structure_test_files"],
    image = ":strategy_monitor_ui",
)
