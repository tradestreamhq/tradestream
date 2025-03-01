java_library(
    name = "argparse4j",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:net_sourceforge_argparse4j_argparse4j",
    ],
)

java_library(
    name = "auto_factory",
    exported_plugins = [
        ":auto_factory_plugin",
    ],
    plugins = [
        ":auto_factory_plugin",
    ],
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:com_google_auto_auto_common",
        "@tradestream_maven//:com_google_auto_factory_auto_factory",
        "@tradestream_maven//:javax_annotation_javax_annotation_api",
        "@tradestream_maven//:javax_inject_javax_inject",
    ],
)

java_plugin(
    name = "auto_factory_plugin",
    processor_class = "com.google.auto.factory.processor.AutoFactoryProcessor",
    deps = [
        "@tradestream_maven//:com_google_auto_auto_common",
        "@tradestream_maven//:com_google_auto_factory_auto_factory",
        "@tradestream_maven//:javax_annotation_javax_annotation_api",
        "@tradestream_maven//:javax_inject_javax_inject",
    ],
)

java_library(
    name = "auto_value",
    exported_plugins = [
        ":auto_value_plugin",
    ],
    neverlink = 1,
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:com_google_auto_value_auto_value",
        "@tradestream_maven//:com_google_auto_value_auto_value_annotations",
    ],
)

java_library(
    name = "auto_value_gson",
    exported_plugins = [
        ":auto_value_gson_plugin",
    ],
    neverlink = 1,
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:com_google_code_gson_gson",
        "@tradestream_maven//:com_ryanharter_auto_value_auto_value_gson",
        "@tradestream_maven//:com_ryanharter_auto_value_auto_value_gson_annotations",
        "@tradestream_maven//:com_ryanharter_auto_value_auto_value_gson_factory",
    ],
)

java_plugin(
    name = "auto_value_plugin",
    processor_class = "com.google.auto.value.processor.AutoValueProcessor",
    deps = [
        "@tradestream_maven//:com_google_auto_value_auto_value",
        "@tradestream_maven//:com_ryanharter_auto_value_auto_value_gson_factory",
    ],
)

java_plugin(
    name = "auto_value_gson_plugin",
    processor_class = "com.ryanharter.auto.value.gson.factory.AutoValueGsonAdapterFactoryProcessor",
    deps = [
        "@tradestream_maven//:com_ryanharter_auto_value_auto_value_gson",
    ],
)

java_library(
    name = "beam_runners_direct_java",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:org_apache_beam_beam_runners_direct_java",
    ],
)

java_library(
    name = "beam_runners_flink_java",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:org_apache_beam_beam_runners_flink_1_18",
    ],
)

java_library(
    name = "beam_sdks_java_core",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:org_apache_beam_beam_sdks_java_core",
    ],
)

java_library(
    name = "beam_sdks_java_extensions_protobuf",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:org_apache_beam_beam_sdks_java_extensions_protobuf",
    ],
)

java_library(
    name = "beam_sdks_java_io_kafka",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:org_apache_beam_beam_sdks_java_io_kafka",
    ],
)

java_library(
    name = "beam_sdks_java_test_utils",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:org_apache_beam_beam_sdks_java_test_utils",
    ],
    testonly = True,
)

java_library(
    name = "flogger",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:com_google_flogger_flogger",
    ],
    runtime_deps = [
        ":flogger_system_backend",
    ],
)

java_library(
    name = "flogger_system_backend",
    exports = [
        "@tradestream_maven//:com_google_flogger_flogger_system_backend",
    ],
)

java_library(
    name = "gson",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:com_google_code_gson_gson",
    ],
)

java_library(
    name = "guava",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:com_google_guava_guava",
    ],
)

java_library(
    name = "guice",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:com_google_inject_guice",
    ],
)

java_library(
    name = "guice_assistedinject",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:com_google_inject_extensions_guice_assistedinject",
    ],
)

java_library(
    name = "guice_testlib",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:com_google_inject_extensions_guice_testlib",
    ],
    testonly = True,
)

java_library(
    name = "hamcrest",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:org_hamcrest_hamcrest",
    ],
    testonly = True,
)

java_library(
    name = "jenetics",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:io_jenetics_jenetics",
    ],
)

java_library(
    name = "joda_time",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:joda_time_joda_time",
    ],
)

java_library(
    name = "junit",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:junit_junit",
    ],
    testonly = True,
)

java_library(
    name = "kafka_clients",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:org_apache_kafka_kafka_clients",
    ],
)

java_library(
    name = "mockito_core",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:org_mockito_mockito_core",
    ],
    testonly = True,
)

java_library(
    name = "mug",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:com_google_mug_mug",
    ],
)

java_library(
    name = "protobuf_java",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:com_google_protobuf_protobuf_java",
    ],
)

java_library(
    name = "protobuf_java_util",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:com_google_protobuf_protobuf_java_util",
    ],
)

java_library(
    name = "ta4j_core",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:org_ta4j_ta4j_core",
    ],
)

java_library(
    name = "test_parameter_injector",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:com_google_testparameterinjector_test_parameter_injector",
    ],
    testonly = True,
)

java_library(
    name = "truth",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:com_google_truth_truth",
    ],
    testonly = True,
)

java_library(
    name = "xchange_core",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:org_knowm_xchange_xchange_core",
    ],
)

java_library(
    name = "xchange_stream_core",
    visibility = ["//visibility:public"],
    exports = [
        "@tradestream_maven//:org_knowm_xchange_xchange_stream_core",
    ],
)
