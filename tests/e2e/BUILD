load("@rules_python//python:py_test.bzl", "py_test")

py_test(
    name = "trading_pipeline_e2e_test",
    srcs = ["trading_pipeline_e2e_test.py"],
    deps = [
        "//services/paper_trading:postgres_client_lib",
        "//services/paper_trading:service_lib",
        "//services/portfolio_state:portfolio_state_lib",
        "//services/risk_adjusted_sizing:risk_adjusted_sizing_lib",
        "//services/signal_generator_agent:agent_lib",
        "//third_party/python:pytest",
        "//third_party/python:requests",
    ],
)
