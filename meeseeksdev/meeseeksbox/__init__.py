"""
MeeseeksBox

Base of a framework to write stateless bots on GitHub.

Mainly writte to use the (currently Beta) new GitHub "Integration" API, and
handle authencation of user.
"""

import os
import base64
from .core import Config
from .core import MeeseeksBox

version_info = (0,0,2)

__version__ = '.'.join(map(str,version_info))

def load_config_from_env():
    """
    Load the configuration, for now stored in the environment
    """
    config={}

    integration_id = os.environ.get('GITHUB_INTEGRATION_ID')
    botname = os.environ.get('GITHUB_BOT_NAME', None)
    
    if not integration_id:
        raise ValueError('Please set GITHUB_INTEGRATION_ID')

    if not botname:
        raise ValueError('Need to set a botname')
    if "@" in botname:
        print("Don't include @ in the botname !")

    botname = botname.replace('@','')
    at_botname = '@'+botname
    integration_id = int(integration_id)

    config['key'] = base64.b64decode(bytes(os.environ.get('B64KEY'), 'ASCII'))
    config['botname'] = botname
    config['at_botname'] = at_botname
    config['integration_id'] = integration_id
    config['webhook_secret'] = os.environ.get('WEBHOOK_SECRET')

    return Config(**config).validate()
