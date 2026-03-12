#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable

DEFAULT_TOKEN_VALUES = {
    "dev-token",
    "changeme",
    "change-me",
    "default-token",
    "your-token-here",
    "example-token",
}


def norm(value: str | None) -> str:
    return (value or "").strip()


def is_default_token(value: str | None) -> bool:
    token = norm(value).lower()
    return (not token) or token in DEFAULT_TOKEN_VALUES


def parse_origins(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def print_result(ok: bool, label: str, detail: str) -> None:
    prefix = "PASS" if ok else "FAIL"
    print(f"[{prefix}] {label}: {detail}")


def infer_production_mode() -> bool:
    env_candidates = ("ENVIRONMENT", "APP_ENV", "PYTHON_ENV")
    for name in env_candidates:
        if norm(os.getenv(name)).lower() == "production":
            return True
    return bool(norm(os.getenv("RENDER"))) or bool(norm(os.getenv("RENDER_SERVICE_ID")))


def verify(allow_user_token_flow: bool, production_mode: bool | None = None) -> int:
    if production_mode is None:
        production_mode = infer_production_mode()
    failures = 0

    api_base = norm(os.getenv("NEXT_PUBLIC_API_BASE_URL"))
    web_token = norm(os.getenv("NEXT_PUBLIC_API_TOKEN"))
    api_token = norm(os.getenv("API_AUTH_TOKEN"))
    cors_origins = parse_origins(os.getenv("API_CORS_ORIGINS"))

    ok = bool(api_base)
    print_result(ok, "NEXT_PUBLIC_API_BASE_URL", api_base or "missing")
    failures += 0 if ok else 1

    if allow_user_token_flow:
        ok = True
        detail = (
            "NEXT_PUBLIC_API_TOKEN is optional because --allow-user-token-flow is enabled; "
            "users must provide token via login/localStorage"
        )
        print_result(ok, "NEXT_PUBLIC_API_TOKEN", detail)
    else:
        ok = bool(web_token) and not is_default_token(web_token)
        detail = "configured" if ok else "missing or default-like token"
        print_result(ok, "NEXT_PUBLIC_API_TOKEN", detail)
        failures += 0 if ok else 1

    ok = bool(api_token) and not is_default_token(api_token)
    detail = "configured" if ok else "missing or default-like token"
    print_result(ok, "API_AUTH_TOKEN", detail)
    failures += 0 if ok else 1

    if production_mode:
        ok = len(cors_origins) > 0
        detail = ", ".join(cors_origins) if cors_origins else "missing"
        print_result(ok, "API_CORS_ORIGINS", detail)
        failures += 0 if ok else 1
    else:
        print_result(True, "API_CORS_ORIGINS", ", ".join(cors_origins) if cors_origins else "not set (allowed in non-production mode)")

    if web_token and api_token:
        ok = web_token == api_token
        print_result(
            ok,
            "Token alignment",
            "NEXT_PUBLIC_API_TOKEN matches API_AUTH_TOKEN" if ok else "tokens differ; requests may fail with 401",
        )
        failures += 0 if ok else 1
    elif allow_user_token_flow and api_token:
        print_result(True, "Token alignment", "skipped strict match because user token flow is enabled")

    if failures:
        print(f"\nEnvironment verification failed with {failures} issue(s).")
        return 1

    print("\nEnvironment verification passed.")
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify web/API deployment environment variable alignment.")
    parser.add_argument(
        "--allow-user-token-flow",
        action="store_true",
        help="Allow NEXT_PUBLIC_API_TOKEN to be omitted when token is supplied by user login flow.",
    )
    parser.add_argument(
        "--production-mode",
        action="store_true",
        help="Force production checks (API_CORS_ORIGINS required). By default this is auto-detected from ENVIRONMENT/APP_ENV/PYTHON_ENV or Render env vars.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    production_mode = True if args.production_mode else None
    return verify(allow_user_token_flow=args.allow_user_token_flow, production_mode=production_mode)


if __name__ == "__main__":
    raise SystemExit(main())
