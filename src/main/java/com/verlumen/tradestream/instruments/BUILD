load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "coin_market_cap_config",
    srcs = ["CoinMarketCapConfig.java"],
)

java_library(
    name = "currency",
    srcs = ["Currency.java"],
    deps = [
        "//third_party:auto_value",
    ],
)

java_library(
    name = "currency_pair",
    srcs = ["CurrencyPair.java"],
    deps = [
        "//third_party:auto_value",
        "//third_party:guava",
        ":currency",
    ],
)

java_library(
    name = "currency_pair_metadata",
    srcs = ["CurrencyPairMetadata.java"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
    ],
)

java_library(
    name = "currency_pair_supply",
    srcs = ["CurrencyPairSupply.java"],
    deps = [
        ":currency_pair_metadata",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//third_party:guava",
    ],
)

java_library(
    name = "currency_pair_supply_impl",
    srcs = ["CurrencyPairSupplyImpl.java"],
    deps = [
        ":currency_pair_metadata",
        ":currency_pair_supply",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//third_party:guava",
    ],
)

java_library(
    name = "currency_pair_supply_provider",
    srcs = ["CurrencyPairSupplyProvider.java"],
    deps = [
        ":coin_market_cap_config",
        ":currency_pair_metadata",
        ":currency_pair_supply",
        ":currency_pair_supply_impl",
        "//src/main/java/com/verlumen/tradestream/http:http_client",
        "//third_party:gson",
        "//third_party:guava",
        "//third_party:guice",
    ],
)

java_library(
    name = "Instruments_module",
    srcs = ["InstrumentsModule.java"],
    deps = [],
)
