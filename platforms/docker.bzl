load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive", "http_file")

def setup_docker_deps():
    http_file(
        name = "jd_darwin_arm64",
        urls = ["https://github.com/josephburnett/jd/releases/download/v1.8.1/jd-arm64-darwin"],
        sha256 = "8b0e51b902650287b7dedc2beee476b96c5d589309d3a7f556334c1baedbec61",
        executable = True,
    )

    http_file(
        name = "jd_darwin_amd64",
        urls = ["https://github.com/josephburnett/jd/releases/download/v1.8.1/jd-amd64-darwin"],
        sha256 = "c5fb5503d2804b1bf631bf12616d56b89711fd451ab233b688ca922402ff3444",
        executable = True,
    )

    http_file(
        name = "jd_linux_amd64",
        urls = ["https://github.com/josephburnett/jd/releases/download/v1.8.1/jd-amd64-linux"],
        sha256 = "ab918f52130561abd4f88d9c2d3ae95d4d56f1a2dff9762665890349d61c763e",
        executable = True,
    )

    http_archive(
        name = "docker_cli_darwin_arm64",
        urls = ["https://download.docker.com/mac/static/stable/aarch64/docker-23.0.0.tgz"],
        integrity = "sha256-naXFF3G/D3a8XieHkd2cm29/SHdheslS3VyI77ep/xA=",
        strip_prefix = "docker",
        build_file_content = 'exports_files(["docker"])',
    )

    http_archive(
        name = "docker_cli_darwin_amd64",
        urls = ["https://download.docker.com/mac/static/stable/x86_64/docker-23.0.0.tgz"],
        integrity = "sha256-55P6RTHVIWEHuEuH8ZHFgu6TeCVPF7WqvPD6MBApOuc=",
        strip_prefix = "docker",
        build_file_content = 'exports_files(["docker"])',
    )

    http_archive(
        name = "docker_cli_linux_amd64",
        urls = ["https://download.docker.com/linux/static/stable/x86_64/docker-23.0.0.tgz"],
        integrity = "sha256-agO72paEW3RRvi9qumnDgWxgqX3jGOg/0bOdG+Ji2K8=",
        strip_prefix = "docker",
        build_file_content = 'exports_files(["docker"])',
    )

    http_archive(
        name = "docker_cli_linux_arm64",
        urls = ["https://download.docker.com/linux/static/stable/aarch64/docker-23.0.0.tgz"],
        integrity = "sha256-2919ff3448187d4f13cfbe2332707cff3f6dcf2baaac42a34bea8dd21f434f4a",
        strip_prefix = "docker",
        build_file_content = 'exports_files(["docker"])',
    )
