package(default_visibility = ["//visibility:public"])

java_library(
    name = "common",
    exports = ["@com_google_auto_auto_common//jar"],
)

java_plugin(
    name = "auto_value_processor",
    processor_class = "com.google.auto.value.processor.AutoValueProcessor",
    visibility = ["//visibility:private"],
    deps = [
        ":common",
        ":service",
        "//third_party/java/guava",
        "@com_google_auto_value_auto_value//jar",
    ],
)

java_plugin(
    name = "auto_annotation_processor",
    processor_class = "com.google.auto.value.processor.AutoAnnotationProcessor",
    visibility = ["//visibility:private"],
    deps = [
        ":common",
        ":service",
        "//third_party/java/guava",
        "@com_google_auto_value_auto_value//jar",
    ],
)

java_plugin(
    name = "auto_oneof_processor",
    processor_class = "com.google.auto.value.processor.AutoOneOfProcessor",
    visibility = ["//visibility:private"],
    deps = [
        ":common",
        ":service",
        "//third_party/java/guava",
        "@com_google_auto_value_auto_value//jar",
    ],
)

java_library(
    name = "autovalue",
    exported_plugins = [
        ":auto_annotation_processor",
        ":auto_oneof_processor",
        ":auto_value_processor",
    ],
    tags = ["maven:compile_only"],
    exports = [
        # "//third_party/java/jsr250_annotations",  # TODO(ronshapiro) Can this be removed?
        "@maven//:com_google_auto_value_auto_value_annotations",
    ],
)

java_plugin(
    name = "auto_factory_processor",
    generates_api = 1,
    processor_class = "com.google.auto.factory.processor.AutoFactoryProcessor",
    visibility = ["//visibility:private"],
    deps = [
        ":common",
        ":service",
        "//third_party/java/guava",
        "//third_party/java/javapoet",
        "@maven//:com_google_auto_factory_auto_factory",
    ],
)

java_library(
    name = "autofactory",
    exported_plugins = [":auto_factory_processor"],
    exports = ["@maven//:com_google_auto_factory_auto_factory"],
)

java_plugin(
    name = "auto_service_processor",
    processor_class = "com.google.auto.service.processor.AutoServiceProcessor",
    visibility = ["//visibility:private"],
    deps = [
        ":common",
        "//third_party/java/guava",
        "@maven//:com_google_auto_service_auto_service",
    ],
)

java_library(
    name = "service",
    exported_plugins = [":auto_service_processor"],
    tags = ["maven:compile_only"],
    exports = ["@maven//:com_google_auto_service_auto_service"],
)
