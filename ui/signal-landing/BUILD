load("@rules_python//python:defs.bzl", "py_binary", "py_test")

filegroup(
    name = "static_files",
    srcs = glob([
        "*.html",
        "*.js",
        "*.css",
    ]),
)

py_binary(
    name = "http_server",
    srcs = ["http_server.py"],
    data = [":static_files"],
    deps = [],
)

py_binary(
    name = "app",
    srcs = ["http_server.py"],
    data = [":static_files"],
    main = "http_server.py",
    deps = [],
)

py_test(
    name = "landing_page_test",
    size = "small",
    timeout = "short",
    srcs = ["landing_page_test.py"],
    data = [":static_files"],
    main = "landing_page_test.py",
    python_version = "PY3",
    deps = [],
)
