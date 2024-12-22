java_library(
    name = "auto_factory",
    exported_plugins = [
        ":auto_factory_plugin",
    ],
    neverlink = 1,
    visibility = ["//visibility:public"],
    exports = [
        "@maven//:com_google_auto_auto_common",
        "@maven//:com_google_auto_factory_auto_factory",
        "@maven//:javax_annotation_javax_annotation_api",
        "@maven//:javax_inject_javax_inject",
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
        "@maven//:com_google_auto_value_auto_value",
        "@maven//:com_google_auto_value_auto_value_annotations",
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
        "@maven//:com_google_code_gson_gson",
        "@maven//:com_ryanharter_auto_value_auto_value_gson",
        "@maven//:com_ryanharter_auto_value_auto_value_gson_annotations",
        "@maven//:com_ryanharter_auto_value_auto_value_gson_factory",
    ],
)

java_plugin(
    name = "auto_factory_plugin",
    processor_class = "com.google.auto.factory.processor.AutoFactoryProcessor",
    deps = [
        "@maven//:com_google_auto_auto_common",
        "@maven//:com_google_auto_factory_auto_factory",
        "@maven//:javax_annotation_javax_annotation_api",
        "@maven//:javax_inject_javax_inject",
    ],
)

java_plugin(
    name = "auto_value_plugin",
    processor_class = "com.google.auto.value.processor.AutoValueProcessor",
    deps = [
        "@maven//:com_google_auto_value_auto_value",
        "@maven//:com_ryanharter_auto_value_auto_value_gson_factory",
    ],
)

java_plugin(
    name = "auto_value_gson_plugin",
    processor_class = "com.ryanharter.auto.value.gson.factory.AutoValueGsonAdapterFactoryProcessor",
    deps = [
        "@maven//:com_ryanharter_auto_value_auto_value_gson",
    ],
)

java_library(
    name = "flogger",
    visibility = ["//visibility:public"],
    exports = [
        "@maven//:com_google_flogger_flogger",
    ],
)

java_library(
    name = "flogger_system_backend",
    neverlink = 1,
    visibility = ["//visibility:public"],
    exports = [
        "@maven//:com_google_flogger_flogger_system_backend",
    ],
)

java_library(
    name = "guava",
    visibility = ["//visibility:public"],
    exports = [
        "@maven//:com_google_guava_guava",
    ],
)

java_library(
    name = "guice",
    visibility = ["//visibility:public"],
    exports = [
        "@maven//:com_google_inject_guice",
    ],
)

java_library(
    name = "guice_assistedinject",
    visibility = ["//visibility:public"],
    exports = [
        "@maven//:com_google_inject_extensions_guice_assistedinject",
    ],
)

java_library(
    name = "kafka_clients",
    visibility = ["//visibility:public"],
    exports = [
        "@maven//:org_apache_kafka_kafka_clients",
    ],
)
