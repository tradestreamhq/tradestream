load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "alembic_migrations",
    srcs = glob(
        ["*.py"],
        exclude = ["*_test.py"],
    ) + glob(["versions/*.py"]),
    data = [
        "alembic.ini",
        "script.py.mako",
    ],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/python:alembic",
        "//third_party/python:psycopg2_binary",
    ],
)

py_binary(
    name = "run_migrations",
    srcs = ["run_migrations.py"],
    main = "run_migrations.py",
    deps = [
        ":alembic_migrations",
    ],
)

py_test(
    name = "alembic_test",
    srcs = ["alembic_test.py"],
    deps = [
        ":alembic_migrations",
        "//third_party/python:alembic",
        "//third_party/python:pytest",
    ],
)
