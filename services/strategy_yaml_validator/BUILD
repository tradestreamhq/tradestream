load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "schema_lib",
    srcs = ["schema.py"],
    deps = [
        "//experiments/llm_validation:strategy_schema",
    ],
)

py_library(
    name = "validator_lib",
    srcs = ["validator.py"],
    deps = [
        ":schema_lib",
        "//third_party/python:jsonschema",
        "//third_party/python:pyyaml",
    ],
)

py_library(
    name = "migrate_lib",
    srcs = ["migrate.py"],
)

py_binary(
    name = "validate_strategy",
    srcs = ["__main__.py"],
    main = "__main__.py",
    deps = [
        ":migrate_lib",
        ":validator_lib",
    ],
)

py_test(
    name = "validator_test",
    srcs = ["validator_test.py"],
    main = "validator_test.py",
    deps = [
        ":validator_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "migrate_test",
    srcs = ["migrate_test.py"],
    main = "migrate_test.py",
    deps = [
        ":migrate_lib",
        ":validator_lib",
        "//third_party/python:pytest",
        "//third_party/python:pyyaml",
    ],
)
