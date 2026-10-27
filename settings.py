"""Who the outreach is from. Override any of these in .env.

Read at call time (not import time) because app/main.py loads .env after its imports.
"""
import os

DEFAULT_COMPANY_NAME = "My Lease AI"
DEFAULT_COMPANY_PITCH = (
    "a SaaS that automates leasing communication for residential property "
    "managers (24/7 prospect follow-up, tour scheduling, lead nurturing)"
)
DEFAULT_SENDER_NAME = "Prakash"


def company_name() -> str:
    return os.getenv("COMPANY_NAME") or DEFAULT_COMPANY_NAME


def company_pitch() -> str:
    return os.getenv("COMPANY_PITCH") or DEFAULT_COMPANY_PITCH


def sender_name() -> str:
    return os.getenv("SENDER_NAME") or DEFAULT_SENDER_NAME
