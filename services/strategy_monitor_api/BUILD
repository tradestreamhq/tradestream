load("@rules_python//python:defs.bzl", "py_binary", "py_library")
load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")

py_library(
    name = "strategy_monitor_api_lib",
    srcs = ["main.py"],
    deps = [
        "//third_party/python:psycopg2_binary",
        "//third_party/python:absl_py",
    ],
)

py_binary(
    name = "strategy_monitor_api",
    srcs = ["main.py"],
    main = "main.py",
    deps = [":strategy_monitor_api_lib"],
)

# --- OCI Image Rules ---
py_image_layer(
    name = "layers",
    binary = ":strategy_monitor_api",
)

oci_image(
    name = "image",
    base = "@python_3_13_slim",
    entrypoint = ["/services/strategy_monitor_api/strategy_monitor_api"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/strategy_monitor_api",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_strategy_monitor_api_image",
    image = ":images",
    repository = "tradestreamhq/strategy-monitor-api",
)
