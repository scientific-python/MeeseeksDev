"""
Meeseeksbox main app module
"""
import os
import base64
import signal

org_whitelist = [
    "MeeseeksBox",
    "Jupyter",
    "IPython",
    "JupyterLab",
    "Carreau",
    "matplotlib",
    "scikit-learn",
    "pandas-dev",
    "scikit-image",
]

usr_blacklist = []

usr_whitelist = [
    "Carreau",
    "gnestor",
    "ivanov",
    "fperez",
    "mpacer",
    "minrk",
    "takluyver",
    "sylvaincorlay",
    "ellisonbg",
    "blink1073",
    "damianavila",
    "jdfreder",
    "rgbkrk",
    "tacaswell",
    "willingc",
    "jhamrick",
    "lgpage",
    "jasongrout",
    "ian-r-rose",
    # matplotlib people
    "tacaswell",
    "QuLogic",
    "anntzer",
    "NelleV",
    "dstansby",
    "efiring",
    "choldgraf",
    "dstansby",
    "dopplershift",
    "jklymak",
    "weathergod",
    "timhoffm",
    # pandas-dev
    "jreback",
    "jorisvandenbossche",
    "gfyoung",
    "TomAugspurger",
]

# https://github.com/integrations/meeseeksdev/installations/new
# already ? https://github.com/organizations/MeeseeksBox/settings/installations/4268
# https://github.com/integration/meeseeksdev


def load_config_from_env():
    """
    Load the configuration, for now stored in the environment
    """
    config = {}

    integration_id = os.environ.get("GITHUB_INTEGRATION_ID")
    botname = os.environ.get("GITHUB_BOT_NAME", None)

    if not integration_id:
        raise ValueError("Please set GITHUB_INTEGRATION_ID")

    if not botname:
        raise ValueError("Need to set a botname")
    if "@" in botname:
        print("Don't include @ in the botname !")

    botname = botname.replace("@", "")
    at_botname = "@" + botname
    integration_id = int(integration_id)

    config["key"] = base64.b64decode(bytes(os.environ.get("B64KEY"), "ASCII"))
    config["botname"] = botname
    config["at_botname"] = at_botname
    config["integration_id"] = integration_id
    config["webhook_secret"] = os.environ.get("WEBHOOK_SECRET")
    config["port"] = int(os.environ.get("PORT", 5000))
    # config option to forward requests as-is to a test server.
    config["forward_staging_url"] = os.environ.get("FORWARD_STAGING_URL", "")
    print("saw config forward", config["forward_staging_url"])

    # Despite their names, this are not __your__ account, but an account created
    # for some functionalities of mr-meeseeks. Indeed, github does not allow
    # cross repositories pull-requests with Applications, so I use a personal
    # account just for that.
    config["personal_account_name"] = os.environ.get("PERSONAL_ACCOUNT_NAME")
    config["personal_account_token"] = os.environ.get("PERSONAL_ACCOUNT_TOKEN")

    return Config(**config).validate()


from .meeseeksbox.core import MeeseeksBox
from .meeseeksbox.core import Config
from .meeseeksbox.commands import (
    replyuser,
    zen,
    tag,
    untag,
    blackify,
    black_suggest,
    precommit,
    quote,
    say,
    debug,
    party,
    safe_backport,
)
from .commands import (
    close,
    open as _open,
    migrate_issue_request,
    ready,
    merge,
    help_make,
)

green = "\x1b[0;32m"
yellow = "\x1b[0;33m"
blue = "\x1b[0;34m"
red = "\x1b[0;31m"
normal = "\x1b[0m"


def main():
    print(blue + "====== (re) starting ======" + normal)
    config = load_config_from_env()

    app_v = os.environ.get("HEROKU_RELEASE_VERSION", None)
    if app_v:
        import keen

        keen.add_event("deploy", {"version": int(app_v[1:])})
    config.org_whitelist = org_whitelist + [o.lower() for o in org_whitelist]
    config.user_whitelist = usr_whitelist + [u.lower() for u in usr_whitelist]
    config.user_blacklist = usr_blacklist + [u.lower() for u in usr_blacklist]
    commands = {
        "hello": replyuser,
        "zen": zen,
        "backport": safe_backport,
        "safe_backport": safe_backport,
        "migrate": migrate_issue_request,
        "tag": tag,
        "untag": untag,
        "open": _open,
        "close": close,
        "autopep8": blackify,
        "reformat": blackify,
        "black": blackify,
        "suggestions": black_suggest,
        "precommit": precommit,
        "ready": ready,
        "merge": merge,
        "say": say,
        "debug": debug,
        "party": party,
    }
    commands["help"] = help_make(commands)
    box = MeeseeksBox(commands=commands, config=config)

    signal.signal(signal.SIGTERM, box.sig_handler)
    signal.signal(signal.SIGINT, box.sig_handler)

    box.start()


if __name__ == "__main__":
    main()
