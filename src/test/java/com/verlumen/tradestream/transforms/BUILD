load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "GetLastNElementsDoFnTest",
    srcs = ["GetLastNElementsDoFnTest.java"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/transforms:get_last_n_elements_do_fn",
        "//third_party:auto_value",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_test_utils",
        "//third_party:commons_collections4",
        "//third_party:guava",
        "//third_party:hamcrest",
        "//third_party:joda_time",
        "//third_party:junit",
    ],
    runtime_deps = [
        "//third_party:beam_runners_direct_java",
    ],
)
