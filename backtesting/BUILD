# load("@rules_python//python:defs.bzl", "py_library", "py_binary", "py_test")
load("@pip//:requirements.bzl", "requirement")

py_library(
    name = "ga_service_lib",
    srcs = ["ga_service.py"],
    deps = [
        requirement("grpcio"),
        requirement("optuna"),
        requirement("numpy"),
        "//protos:backtesting_py_grpc",
        "//protos:backtesting_py_proto",
        "//protos:strategies_py_proto",
        ":optimization",
    ],
)

# py_library(
#     name = "optimization",
#     srcs = ["optimization.py"],
#     deps = [
#         requirement("optuna"),
#         requirement("numpy"),
#     ],
# )

# py_binary(
#     name = "ga_service",
#     srcs = ["ga_service.py"],
#     main = "ga_service.py", 
#     deps = [":ga_service_lib"],
# )

# py_test(
#     name = "ga_service_test",
#     srcs = ["ga_service_test.py"],
#     deps = [
#         ":ga_service_lib",
#         requirement("pytest"),
#         requirement("grpcio-testing"),
#     ],
# )

# py_test(
#     name = "optimization_test", 
#     size = "small",
#     srcs = ["optimization_test.py"],
#     deps = [
#         ":optimization",
#         requirement("pytest"),
#     ],
# )
