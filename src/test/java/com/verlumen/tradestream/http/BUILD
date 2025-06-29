load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "HttpClientImplTest",
    srcs = ["HttpClientImplTest.java"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/http:http_client_impl",
        "//src/main/java/com/verlumen/tradestream/http:http_url_connection_factory",
        "//third_party/java:guice",
        "//third_party/java:guice_testlib",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:truth",
    ],
)
