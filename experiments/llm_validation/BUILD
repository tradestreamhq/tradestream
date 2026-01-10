load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "strategy_schema",
    srcs = ["strategy_schema.py"],
    deps = [
        "//third_party/python:pyyaml",
    ],
)

py_library(
    name = "llm_generator",
    srcs = ["llm_generator.py"],
    deps = [
        ":strategy_schema",
        "//third_party/python:anthropic",
        "//third_party/python:pyyaml",
    ],
)

py_binary(
    name = "run_experiment_1",
    srcs = ["llm_generator.py"],
    main = "llm_generator.py",
    deps = [
        ":llm_generator",
    ],
)

py_test(
    name = "strategy_schema_test",
    srcs = ["test_strategy_schema.py"],
    main = "test_strategy_schema.py",
    deps = [
        ":strategy_schema",
        "//third_party/python:pytest",
    ],
)
