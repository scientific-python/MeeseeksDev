import os
import base64
from core import Config

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

from .core import MeeseeksBox
from .commands import replyuser, zen, backport, migrate_issue_request, tag, untag

def main():
    print('====== (re) starting ======')
    config = load_config_from_env()
    MeeseeksBox(commands={
            'hello': replyuser,
            'zen': zen,
            'backport': backport,
            'migrate': migrate_issue_request,
            'tag': tag,
            'untag': untag
        }, config=config).start()

if __name__ == "__main__":
    main()
