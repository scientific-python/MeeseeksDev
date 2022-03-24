"""
MeeseeksBox

Base of a framework to write stateless bots on GitHub.

Mainly writte to use the (currently Beta) new GitHub "Integration" API, and
handle authencation of user.
"""

from .core import Config  # noqa
from .core import MeeseeksBox  # noqa

version_info = (0, 0, 2)

__version__ = ".".join(map(str, version_info))
