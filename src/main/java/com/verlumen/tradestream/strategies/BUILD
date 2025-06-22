load("@rules_java//java:defs.bzl", "java_library")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility = ["//visibility:public"])

kt_jvm_library(
    name = "momentum_indicator",
    srcs = ["MomentumIndicator.kt"],
    deps = [
        "//third_party/java:ta4j_core",
    ],
)

kt_jvm_library(
    name = "strategy_constants",
    srcs = ["StrategyConstants.kt"],
    deps = [
        "//protos:strategies_java_proto",
    ],
)

java_library(
    name = "strategy_factory",
    srcs = ["StrategyFactory.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)

kt_jvm_library(
    name = "strategy_specs",
    srcs = [
        "StrategySpec.kt",
        "StrategySpecs.kt",
    ],
    visibility = ["//visibility:public"],
    deps = [
        # Core interfaces required by the spec definitions
        ":strategy_factory",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",

        # Implementations for each strategy included in the map
        "//src/main/java/com/verlumen/tradestream/strategies/adxstochastic:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/adxstochastic:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/atrcci:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/atrcci:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/atrtrailingstop:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/atrtrailingstop:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/bbandwr:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/bbandwr:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/chaikinoscillator:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/chaikinoscillator:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/cmfzeroline:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/cmfzeroline:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/donchianbreakout:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/donchianbreakout:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/doubleemacrossover:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/doubleemacrossover:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/emamacd:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/emamacd:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/heikenashi:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/heikenashi:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/ichimokucloud:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/ichimokucloud:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/kstoscillator:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/kstoscillator:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/macdcrossover:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/macdcrossover:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/massindex:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/massindex:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/momentumpinball:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/momentumpinball:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/momentumsmacrossover:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/momentumsmacrossover:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/parabolicsarr:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/parabolicsarr:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/rsiemacrossover:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/rsiemacrossover:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/rvi:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/rvi:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/smaemacrossover:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/smaemacrossover:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/smarsi:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/smarsi:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/stochasticsrsi:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/stochasticsrsi:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/tripleemacrossover:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/tripleemacrossover:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/volatilitystop:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/volatilitystop:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/vwapcrossover:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/vwapcrossover:strategy_factory",
    ],
)
