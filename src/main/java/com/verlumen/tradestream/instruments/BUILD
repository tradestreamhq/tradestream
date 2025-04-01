load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "coin_market_cap_config",
    srcs = ["CoinMarketCapConfig.java"],
)

java_library(
    name = "currency",
    srcs = ["Currency.java"],
)

java_library(
    name = "currency_pair",
    srcs = ["CurrencyPair.java"],
    deps = [
        ":currency",
        "//third_party:guava",
    ],
)

java_library(
    name = "currency_pair_provider",
    srcs = ["CurrencyPairProvider.java"],
    deps = [
        ":coin_market_cap_config",
        "//src/main/java/com/verlumen/tradestream/http:http_client",
        "//third_party:gson",
        "//third_party:guava",
        "//third_party:guice",
    ],
)

java_library(
    name = "instruments_module",
    srcs = ["InstrumentsModule.java"],
    deps = [
        ":coin_market_cap_config",
        ":currency_pair",
        ":currency_pair_provider",
        "//third_party:auto_value",
        "//third_party:guava",
        "//third_party:guice",
    ],
)
