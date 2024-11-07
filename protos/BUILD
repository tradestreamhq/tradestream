load("@protobuf//bazel:proto_library.bzl", "proto_library")
load("@rules_java//java:defs.bzl", "java_library", "java_binary", "java_test")
load("@rules_proto//proto:defs.bzl", "proto_library", "java_proto_library")

proto_library(
    name = "marketdata_proto",
    srcs = ["src/main/java/com/example/marketdata/marketdata.proto"],
    visibility = ["//visibility:public"],
)

java_proto_library(
    name = "marketdata_java_proto",
    deps = [":marketdata_proto"],
    visibility = ["//visibility:public"],
)

# Java library
java_library(
    name = "marketdata_lib",
    srcs = glob(["src/main/java/**/*.java"]),
    deps = [
        ":marketdata_java_proto",
        "@maven//:org_knowm_xchange_xchange_stream_core",
        "@maven//:org_knowm_xchange_xchange_kraken",
        "@maven//:io_reactivex_rxjava2_rxjava",
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_protobuf_protobuf_java",
        "@maven//:org_apache_kafka_kafka_clients",
        "@maven//:org_slf4j_slf4j_api",
    ],
    visibility = ["//visibility:public"],
)

# Main Java binary
java_binary(
    name = "marketdata_main",
    main_class = "com.example.Main",
    runtime_deps = [":marketdata_lib"],
)

# Java unit test
java_test(
    name = "marketdata_test",
    srcs = glob(["src/test/java/**/*.java"]),
    deps = [
        ":marketdata_lib",
        "@maven//:junit_junit",
        "@maven//:org_mockito_mockito_core",
    ],
)

