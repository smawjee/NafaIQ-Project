from slowapi import Limiter
from slowapi.util import get_remote_address

# NOTE: `default_limits` only takes effect when `SlowAPIMiddleware` is added to
# the app. main.py deliberately does NOT add it — a blanket 60/minute would
# throttle the frontend's high-frequency market-snapshot polling. So this
# default is inert and every route that needs a limit must carry an explicit
# `@limiter.limit(...)` decorator. Kept as the value to use if the middleware is
# ever enabled; do not rely on it for protection today.
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
