load("@rules_java//java:defs.bzl", "java_proto_library")
load("@rules_proto//proto:defs.bzl", "proto_library")

proto_library(
    name = "marketdata_proto",
    srcs = ["marketdata.proto"],
    visibility = ["//visibility:public"],
)

java_proto_library(
    name = "marketdata_java_proto",
    deps = [":marketdata_proto"],
    visibility = ["//visibility:public"],
)
