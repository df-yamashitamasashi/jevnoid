from __future__ import annotations

import os


def read_secret(env_name: str, param_env_name: str) -> str | None:
    """Plain env var for local development; otherwise the SSM SecureString named by `param_env_name`."""
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    parameter_name = os.environ.get(param_env_name, "").strip()
    if not parameter_name:
        return None
    import boto3

    response = boto3.client("ssm").get_parameter(Name=parameter_name, WithDecryption=True)
    return response["Parameter"]["Value"].strip() or None
