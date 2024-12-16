load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "DataConsumptionLayerImplTest",
    size = "small",
    srcs = ["DataConsumptionLayerImplTest.java"],
    deps = [
        ":data_consumption",
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_inject_guice",
        "@maven//:com_google_inject_extensions_guice_testlib",
        "@maven//:com_google_truth_truth",
        "@maven//:junit_junit",
        "@maven//:org_mockito_mockito_core",
        "//protos:marketdata_java_proto",
    ],
)
