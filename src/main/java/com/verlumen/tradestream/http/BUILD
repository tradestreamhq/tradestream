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
        ":http_client",
        ":http_url_connection_factory",
        "//third_party:flogger",
        "//third_party:guice",
    ],
)

java_library(
    name = "http_module",
    srcs = ["HttpModule.java"],
    deps = [
        ":http_client",
        ":http_client_impl",
        ":http_url_connection_factory",
        ":http_url_connection_factory_impl",
        "//third_party:guice",
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
        ":http_url_connection_factory",
        "//third_party:guice",
    ],
)
