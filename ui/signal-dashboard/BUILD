load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")

# Static content files (Vite build output goes to dist/)
filegroup(
    name = "static_files",
    srcs = glob([
        "dist/**/*.html",
        "dist/**/*.js",
        "dist/**/*.css",
        "dist/**/*.svg",
    ]),
)

# Custom nginx configuration
tar(
    name = "nginx_config_tar",
    srcs = ["nginx.conf"],
)

# Package dist files for nginx html directory
tar(
    name = "static_tar",
    srcs = [":static_files"],
)

# Signal Dashboard UI using nginx
oci_image(
    name = "signal_dashboard_ui",
    base = "@nginx_alpine",
    cmd = ["cp /ui/signal-dashboard/nginx.conf /etc/nginx/nginx.conf && nginx -g 'daemon off;'"],
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
    name = "signal_dashboard_ui_images",
    images = [
        ":signal_dashboard_ui",
    ],
)

# Push target for the UI image
oci_push(
    name = "push_signal_dashboard_ui_image",
    image = ":signal_dashboard_ui_images",
    repository = "ghcr.io/tradestreamhq/signal-dashboard-ui",
)

# Load target for the UI image
oci_load(
    name = "load_signal_dashboard_ui_image",
    image = ":signal_dashboard_ui",
    repo_tags = ["signal-dashboard-ui:latest"],
)

filegroup(
    name = "signal_dashboard_ui_tarball",
    srcs = [":load_signal_dashboard_ui_image"],
    output_group = "tarball",
)

# Container structure test
container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":signal_dashboard_ui",
    tags = ["requires-docker"],
)
