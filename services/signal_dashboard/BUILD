load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:defs.bzl", "py_binary", "py_test")

# Static content files (only web assets)
filegroup(
    name = "static_files",
    srcs = glob([
        "*.html",
        "*.js",
        "*.css",
    ]),
)

# All files needed for development and testing
filegroup(
    name = "dev_files",
    srcs = glob([
        "*.html",
        "*.js",
        "*.css",
        "*.conf",
        "*.md",
        "*.sh",
    ]),
)

# Package static files for nginx html directory
tar(
    name = "static_tar",
    srcs = [":static_files"],
)

# Custom nginx configuration
tar(
    name = "nginx_config_tar",
    srcs = ["nginx.conf"],
)

# Create a simple HTTP server script (for development/testing only)
py_binary(
    name = "http_server",
    srcs = ["http_server.py"],
    data = [":dev_files"],
    deps = [],
)

# Executable target for running the UI locally
py_binary(
    name = "app",
    srcs = ["http_server.py"],
    data = [":dev_files"],
    main = "http_server.py",
    deps = [],
)

# UI tests
py_test(
    name = "signal_dashboard_ui_test",
    size = "medium",
    timeout = "short",
    srcs = ["ui_test.py"],
    data = [":dev_files"],
    main = "ui_test.py",
    python_version = "PY3",
    deps = [],
)

# Static web server for the Signal Dashboard using nginx
oci_image(
    name = "signal_dashboard",
    base = "@nginx_alpine",
    cmd = ["cp /services/signal_dashboard/nginx.conf /etc/nginx/nginx.conf && cp /services/signal_dashboard/*.html /usr/share/nginx/html/ && nginx -g 'daemon off;'"],
    entrypoint = [
        "/bin/sh",
        "-c",
    ],
    tars = [
        ":static_tar",
        ":nginx_config_tar",
    ],
    workdir = "/usr/share/nginx/html",
)

# OCI image index for multi-platform support
oci_image_index(
    name = "signal_dashboard_images",
    images = [
        ":signal_dashboard",
    ],
)

# Push target for the UI image
oci_push(
    name = "push_signal_dashboard_image",
    image = ":signal_dashboard_images",
    repository = "ghcr.io/tradestreamhq/signal-dashboard",
)

# Load target for the UI image
oci_load(
    name = "load_signal_dashboard_image",
    image = ":signal_dashboard",
    repo_tags = ["signal-dashboard:latest"],
)

filegroup(
    name = "signal_dashboard_tarball",
    srcs = [":load_signal_dashboard_image"],
    output_group = "tarball",
)

# Container structure test
filegroup(
    name = "container_structure_test_files",
    srcs = ["container-structure-test.yaml"],
)

container_structure_test(
    name = "container_test",
    configs = [":container_structure_test_files"],
    image = ":signal_dashboard",
)
