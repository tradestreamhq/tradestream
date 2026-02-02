load("@rules_java//java:defs.bzl", "java_test")

package(default_visibility = ["//visibility:public"])

java_test(
    name = "TimeFrameTest",
    srcs = ["TimeFrameTest.java"],
    test_class = "com.verlumen.tradestream.time.TimeFrameTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/time:time_frame",
        "//third_party/java:junit",
        "//third_party/java:truth",
    ],
)
