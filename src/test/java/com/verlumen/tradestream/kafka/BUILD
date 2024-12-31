load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "KafkaPropertiesTest",
    srcs = ["KafkaPropertiesTest.java"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/kafka:kafka_properties",
        "//third_party:argparse4j",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:truth",
    ],
)
