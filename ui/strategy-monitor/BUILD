load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("@rules_python//python:defs.bzl", "py_binary", "py_test")

# Static content files
filegroup(
    name = "static_files",
    srcs = glob([
        "*.html",
        "*.js", 
        "*.css",
        "*.md",
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
    data = [":static_files"],
    deps = [],
)

# UI tests
py_test(
    name = "strategy_monitor_ui_test",
    size = "medium",
    timeout = "short",
    srcs = ["ui_test.py"],
    data = [":static_files"],
    main = "ui_test.py",
    python_version = "PY3",
    deps = [],
)

# Static web server for the Strategy Monitor UI using nginx
oci_image(
    name = "strategy_monitor_ui",
    base = "@nginx_alpine",
    tars = [
        ":static_tar",
        ":nginx_config_tar",
    ],
    workdir = "/usr/share/nginx/html",
    # Use nginx base image's default entrypoint and cmd
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
