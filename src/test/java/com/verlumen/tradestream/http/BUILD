load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "HttpClientImplTest",
    srcs = ["HttpClientImplTest.java"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/http:http_client_impl",
        "//src/main/java/com/verlumen/tradestream/http:http_url_connection_factory",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:truth",
    ],
)
