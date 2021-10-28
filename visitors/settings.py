from __future__ import annotations

from typing import Optional

from django.conf import settings


def _setting(key: str, default: str) -> str:
    return getattr(settings, key, default)


# session key used to store visitor.uuid
VISITOR_SESSION_KEY: str = _setting("VISITOR_SESSION_KEY", "visitor:session")

# key used to store visitor uuid on querystring
VISITOR_QUERYSTRING_KEY: str = _setting("VISITOR_QUERYSTRING_KEY", "vuid")

# Value used to `request.session.set_expiry` for anonymous users. If the
# request.user is already authenticated we let them carry on with the site
# default - however if the visitor is anonymous we can override the session
# expiry. By default this will be set to 0, which means that the session expires
# when the browser is closed. We do not support datetime or timedelta values
# here - it must be an integer (seconds), or None. see
# https://docs.djangoproject.com/en/3.1/topics/http/sessions/#django.contrib.sessions.backends.base.SessionBase.set_expiry  # noqa
# * If value is an integer, the session will expire after that many seconds of
#   inactivity.
# * If value is None, the session reverts to using the global session expiry
#   policy.
VISITOR_SESSION_EXPIRY: Optional[int] = _setting("VISITOR_SESSION_EXPIRY", 0)

# Value used to set the expiry of the visitor token - the point at which it can
# no longer be used. NB this is separate from the session expiry. Once the token
# is stashed in the session the visitor will remain a visitor until the session
# expires. This value is used by the VisitorRequestMiddleware.
VISITOR_TOKEN_EXPIRY: int = _setting("VISITOR_TOKEN_EXPIRY", 300)


DEFAULT_MAX_LINK_USAGES_ALLOWED: int = _setting("DEFAULT_MAX_LINK_USAGES_ALLOWED", 10)
# Value used to define the default maximum number of usages (visits) per link.
# Each link should have a maximum number of visits to allow and this value
# defines the default max number of visits allowed in case of missing Visitors
# can use a url link to access a specific view. By default this is set to 10
# usages per link.
