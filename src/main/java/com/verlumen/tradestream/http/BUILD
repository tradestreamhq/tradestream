load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "http_client",
    srcs = ["HttpClient.java"],
)

java_library(
    name = "http_client_impl",
    srcs = ["HttpClientImpl.java"],
    deps = [
        "//third_party:flogger",
        "//third_party:guice",
        ":http_client",
        ":http_url_connection_factory",
    ],
)

java_library(
    name = "http_module",
    srcs = ["HttpModule.java"],
    deps = [
        "//third_party:guice",
        ":http_client",
        ":http_client_impl",
        ":http_url_connection_factory",
        ":http_url_connection_factory_impl",
    ],
)

java_library(
    name = "http_url_connection_factory",
    srcs = ["HttpURLConnectionFactory.java"],
)

java_library(
    name = "http_url_connection_factory_impl",
    srcs = ["HttpURLConnectionFactoryImpl.java"],
    deps = [
        "//third_party:guice",
        ":http_url_connection_factory",
    ],
)
