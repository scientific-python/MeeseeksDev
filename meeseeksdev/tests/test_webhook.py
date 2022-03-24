import hmac

import pytest
import tornado.web

from ..meeseeksbox.core import Authenticator, Config, WebHookHandler

commands = {}

config = Config(
    integration_id=100,
    key=None,
    personal_account_token="foo",
    personal_account_name="bar",
    forward_staging_url="",
    webhook_secret="foo",
)

auth = Authenticator(
    config.integration_id, config.key, config.personal_account_token, config.personal_account_name
)

application = tornado.web.Application(
    [
        (
            r"/",
            WebHookHandler,
            {
                "actions": commands,
                "config": config,
                "auth": auth,
            },
        ),
    ]
)


@pytest.fixture
def app():
    return application


async def test_get(http_server_client):
    response = await http_server_client.fetch("/")
    assert response.code == 200


async def test_post(http_server_client):
    body = "{}"
    secret = config.webhook_secret
    assert secret is not None
    sig = "sha1=" + hmac.new(secret.encode("utf8"), body.encode("utf8"), "sha1").hexdigest()
    headers = {"X-Hub-Signature": sig}
    response = await http_server_client.fetch("/", method="POST", body=body, headers=headers)
    assert response.code == 200
