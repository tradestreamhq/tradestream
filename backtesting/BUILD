load("@rules_python//python:py_test.bzl", "py_test")

py_test(
    name = "pricetag_test",
    srcs = ["test.py"],
    main = "test.py",
    deps = [
        "//py_proto_library/example.com/proto:pricetag_proto_py_pb2",
    ],
)
