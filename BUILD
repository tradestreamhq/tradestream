load("@rules_kotlin//kotlin:core.bzl", "define_kt_toolchain")
load("@rules_python//python:pip.bzl", "compile_pip_requirements") 

define_kt_toolchain(
    name = "kotlin_toolchain",
    api_version = "1.9",  # "1.1", "1.2", "1.3", "1.4", "1.5" "1.6", "1.7", "1.8", or "1.9"
    jvm_target = "17", # "1.6", "1.8", "9", "10", "11", "12", "13", "15", "16", "17", "18", "19", "20" or "21"
    language_version = "1.9",  # "1.1", "1.2", "1.3", "1.4", "1.5" "1.6", "1.7", "1.8", or "1.9"
)

compile_pip_requirements(
    name = "requirements",
    timeout = "moderate",
    src = "requirements.in",
    requirements_txt = "requirements_lock.txt",
)
