"""Public links shared by the Recepia commercial assistant."""

from config import settings


def recepia_site_url() -> str:
    return settings.PUBLIC_SITE_URL + "/"


def recepia_signup_url() -> str:
    return settings.PUBLIC_SITE_URL + "/cadastro"
