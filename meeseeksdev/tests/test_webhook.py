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


@pytest.mark.gen_test
def test_get(http_client, base_url):
    response = yield http_client.fetch(base_url)
    assert response.code == 200


@pytest.mark.gen_test
def test_post(http_client, base_url):
    body = "{}"
    secret = config.webhook_secret
    assert secret is not None
    sig = "sha1=" + hmac.new(secret.encode("utf8"), body.encode("utf8"), "sha1").hexdigest()
    headers = {"X-Hub-Signature": sig}
    response = yield http_client.fetch(base_url, method="POST", body=body, headers=headers)
    assert response.code == 200
