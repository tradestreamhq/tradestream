load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "openrouter_client_lib",
    srcs = [
        "__init__.py",
        "openrouter_client.py",
    ],
    deps = [
        "//services/shared:model_config",
        "//third_party/python:openai",
    ],
)

py_library(
    name = "mcp_client_lib",
    srcs = [
        "__init__.py",
        "mcp_client.py",
    ],
    deps = [
        "//third_party/python:requests",
    ],
)

py_library(
    name = "base_lib",
    srcs = [
        "__init__.py",
        "base.py",
    ],
    deps = [
        ":mcp_client_lib",
        ":openrouter_client_lib",
    ],
)

# --- Tests ---

py_test(
    name = "openrouter_client_test",
    srcs = ["openrouter_client_test.py"],
    deps = [
        ":openrouter_client_lib",
        "//third_party/python:openai",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "mcp_client_test",
    srcs = ["mcp_client_test.py"],
    deps = [
        ":mcp_client_lib",
        "//third_party/python:pytest",
        "//third_party/python:requests",
    ],
)

py_test(
    name = "base_test",
    srcs = ["base_test.py"],
    deps = [
        ":base_lib",
        "//third_party/python:pytest",
    ],
)
