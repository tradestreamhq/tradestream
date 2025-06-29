load("@rules_java//java:defs.bzl", "java_library")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

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
        "//third_party/java:guava",
    ],
)

kt_jvm_library(
    name = "currency_pair_supplier",
    srcs = ["CurrencyPairSupplier.kt"],
    deps = [
        ":coin_market_cap_config",
        ":currency_pair",
        "//src/main/java/com/verlumen/tradestream/http:http_client",
        "//third_party/java:gson",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:mug",
    ],
)

java_library(
    name = "instruments_module",
    srcs = ["InstrumentsModule.java"],
    deps = [
        ":coin_market_cap_config",
        ":currency_pair",
        ":currency_pair_supplier",
        "//src/main/java/com/verlumen/tradestream/execution:run_mode",
        "//third_party/java:auto_value",
        "//third_party/java:guava",
        "//third_party/java:guice",
    ],
)
