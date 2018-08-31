import re
import os
import hmac
import time
import datetime
import inspect

import yaml
import base64
import json

import keen

import tornado.web
import tornado.httpserver
import tornado.ioloop

from .utils import Authenticator
from .utils import ACCEPT_HEADER_SYMMETRA
from .scopes import Permission

from yieldbreaker import YieldBreaker

green = "\033[0;32m"
yellow = "\033[0;33m"
red = "\033[0;31m"
normal = "\033[0m"


class Config:
    botname = None
    integration_id = None
    key = None
    botname = None
    at_botname = None
    integration_id = None
    webhook_secret = None
    personnal_account_name = None
    personnal_account_token = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def validate(self):
        missing = [
            attr
            for attr in dir(self)
            if not attr.startswith("_") and getattr(self, attr) is None
        ]
        if missing:
            raise ValueError(
                "The followingg configuration options are missing : {}".format(missing)
            )
        return self


def verify_signature(payload, signature, secret):
    """
    Make sure hooks are encoded correctly
    """
    expected = "sha1=" + hmac.new(secret.encode("ascii"), payload, "sha1").hexdigest()
    return hmac.compare_digest(signature, expected)


class BaseHandler(tornado.web.RequestHandler):
    def error(self, message):
        self.set_status(500)
        self.write({"status": "error", "message": message})

    def success(self, message="", payload={}):
        self.write({"status": "success", "message": message, "data": payload})


class MainHandler(BaseHandler):
    def get(self):
        self.finish("No")


def process_mentionning_comment(body, bot_re):
    """
    Given a comment body and a bot name parse this into a tuple of (command, arguments)
    """
    lines = body.splitlines()
    lines = [
        l.strip()
        for l in lines
        if (bot_re.search(l) and not l.startswith(">")) or l.startswith("!msbox")
    ]
    nl = []
    for l in lines:
        if l.startswith("!msbox"):
            nl.append(l.split("!msbox")[-1].strip())
        else:
            nl.append(bot_re.split(l)[-1].strip())

    command_args = [l.split(" ", 1) for l in nl]
    command_args = [c if len(c) > 1 else (c[0], None) for c in command_args]
    return command_args


class WebHookHandler(MainHandler):
    def initialize(self, actions, config, auth, *args, **kwargs):
        self.actions = actions
        self.config = config
        self.auth = auth
        super().initialize(*args, **kwargs)

    def get(self):
        self.getfinish("Webhook alive and listening")

    def post(self):
        if "X-Hub-Signature" not in self.request.headers:
            keen.add_event("attack", {"type": "no X-Hub-Signature"})
            return self.error("WebHook not configured with secret")

        if not verify_signature(
            self.request.body,
            self.request.headers["X-Hub-Signature"],
            self.config.webhook_secret,
        ):
            keen.add_event("attack", {"type": "wrong signature"})
            return self.error(
                "Cannot validate GitHub payload with " "provided WebHook secret"
            )

        payload = tornado.escape.json_decode(self.request.body)
        org = payload.get("repository", {}).get("owner", {}).get("login")
        if not org:
            org = (
                payload.get("issue", {})
                .get("repository", {})
                .get("owner", {})
                .get("login")
            )
            print("org in issue", org)

        if payload.get("action", None) in [
            "edited",
            "assigned",
            "labeled",
            "opened",
            "created",
            "submitted",
        ]:
            keen.add_event("ignore_org_missing", {"edited": "reason"})
        else:
            if hasattr(self.config, "org_whitelist") and (
                org not in self.config.org_whitelist
            ):
                keen.add_event("post", {"reject_organisation": org})

        sender = payload.get("sender", {}).get("login", {})
        if hasattr(self.config, "user_blacklist") and (
            sender in self.config.user_blacklist
        ):
            keen.add_event("post", {"blocked_user": sender})
            self.finish("Blocked user.")
            return

        action = payload.get("action", None)
        keen.add_event("post", {"accepted_action": action})
        unknown_repo = red + "<unknown repo>" + normal
        repo = payload.get("repository", {}).get("full_name", unknown_repo)
        if repo == unknown_repo:
            import json
            import there

            there.print(json.dumps(payload))
        if payload.get("commits"):
            # TODO
            num = payload.get("size")
            ref = payload.get("ref")
            by = payload.get("pusher", {}).get("name")
            print(yellow + str(list(payload.keys())))
            print(
                green
                + f"(https://github.com/{repo}) `{num}` commit(s) were pushed to `{ref}` by `{by}`"
            )
            self.finish("commits were pushed to {repo}")
            return

        if action:
            return self.dispatch_action(action, payload)
        else:
            event_type = self.request.headers.get("X-GitHub-Event")
            if event_type == "pull_request":
                return self.finish()

            if event_type in {
                "status",
                "fork",
                "deployment_status",
                "deployment",
                "delete",
                "push",
                "create",
            }:
                print(
                    f"(https://github.com/{repo}) Not handling event type `{event_type}` yet."
                )
                return self.finish()

            print(f"({repo}) No action available for the webhook :", event_type)

    @property
    def mention_bot_re(self):
        botname = self.config.botname
        return re.compile("@?" + re.escape(botname) + "(?:\[bot\])?", re.IGNORECASE)

    def dispatch_action(self, type_, payload):
        botname = self.config.botname
        repo = payload.get("repository", {}).get(
            "full_name", red + "<unknown repo>" + normal
        )
        # new issue/PR opened
        if type_ == "opened":
            issue = payload.get("issue", None)
            if not issue:
                pr_number = payload.get("pull_request", {}).get("number", None)
                print(green + f"(https://github.com/{repo}/pull/{pr_number}) `opened`.")
                return self.finish("Not really good, request has no issue")
            if issue:
                user = payload["issue"]["user"]["login"]
                if user == self.config.botname.lower() + "[bot]":
                    return self.finish("Not responding to self")
            # todo dispatch on on-open

        elif type_ == "added":
            installation = payload.get("installation", None)
            if installation and installation.get("account"):
                print(f"({repo}) we got a new installation.")
                self.auth._build_auth_id_mapping()
                return self.finish()
            else:
                pass
                # print("can't deal with this kind of payload yet", payload)
        # new comment created
        elif type_ == "created":
            comment = payload.get("comment", None)
            installation = payload.get("installation", None)
            issue = payload.get("issue", {})
            no_issue_number = red + "<no issue number>" + normal
            if not issue:
                pull_request = payload.get("pull_request", {})
                if pull_request:
                    what = "pulls"
                    number = pull_request.get("number", no_issue_number)
                else:
                    number = no_issue_number
            else:
                what = "issues"
                number = issue.get("number", no_issue_number)

            if number is no_issue_number:
                import json

                print(list(payload.keys()))
            if comment:
                user = payload["comment"]["user"]["login"]
                if user == botname.lower() + "[bot]":
                    print(
                        green
                        + f"(https://github.com/{repo}/{what}/{number}) Not responding to self"
                    )
                    return self.finish("Not responding to self")
                if "[bot]" in user:
                    print(
                        green
                        + f"(https://github.com/{repo}/{what}/{number}) Not responding to another bot ({user})"
                    )
                    return self.finish("Not responding to another bot")
                body = payload["comment"]["body"]
                if self.mention_bot_re.findall(body) or ("!msbox" in body):
                    self.dispatch_on_mention(body, payload, user)
                else:
                    pass
                    # import textwrap
                    # print(f'({repo}/{what}/{number}) Was not mentioned by ',
                    #       #self.config.botname,')\n',
                    #       #textwrap.indent(body,
                    #       user, 'on', f'{what}/{number}')
            elif installation and installation.get("account"):
                print(f"({repo}) we got a new installation.")
                self.auth._build_auth_id_mapping()
                return self.finish()
            else:
                print("not handled", payload)
        elif type_ == "submitted":
            # print(f'({repo}) ignoring `submitted`')
            pass
        else:
            if type_ == "closed":
                is_pr = payload.get("pull_request", {})
                num = is_pr.get("number", "????")
                merged = is_pr.get("merged", None)
                action = is_pr.get("action", None)
                if is_pr:
                    merged_by = is_pr.get("merged_by")
                    print(
                        green
                        + f"(https://github.com/{repo}/pull/{num}) merged (action: {action}, merged:{merged}) by {merged_by}"
                    )
                    if merged_by:
                        description = ""
                        try:
                            raw_labels = is_pr.get("labels", [])
                            if raw_labels:
                                installation_id = payload["installation"]["id"]
                                session = self.auth.session(installation_id)
                                for raw_label in raw_labels:
                                    label = session.ghrequest(
                                        "GET",
                                        raw_label.get("url", ""),
                                        override_accept_header=ACCEPT_HEADER_SYMMETRA,
                                    ).json()
                                    label_desc = label.get("description", "")
                                    # apparently can still be none-like ?
                                    if not label_desc:
                                        label_desc = ""
                                    description += "\n" + label_desc.replace("&", "\n")
                        except:
                            import traceback

                            traceback.print_exc()
                        milestone = is_pr.get("milestone", {})
                        if milestone:
                            e = milestone.get("description", "")
                            if not e:
                                e = ""
                            description += e
                        if (
                            "on-merge:" in description
                            and is_pr["base"]["ref"] == "master"
                        ):
                            did_backport = False
                            for l in description.splitlines():
                                l = l.strip()
                                if l.startswith("on-merge:"):
                                    todo = l[len("on-merge:") :].strip()
                                    self.dispatch_on_mention(
                                        "@meeseeksdev " + todo,
                                        payload,
                                        merged_by["login"],
                                    )
                                    did_backport = True
                            if not did_backport:
                                print(
                                    '"on-merge:" found in milestone description, but unable to parse command.',
                                    'Is "on-merge:" on a separate line?',
                                )
                    else:
                        print(f"({repo}) Hum, closed, PR but not merged")
                else:
                    pass
                    # print("can't deal with `", type_, "` (for issues) yet")
            elif type_ == "milestoned":
                pass
            else:
                pass
                # print(f"({repo}) can't deal with `{type_}` yet")

    # def _action_allowed(args):
    #     """
    #     determine if an action requester can make an action

    #     Typically only
    #       - the requester have a permission higher than the required permission.

    #     Or:
    #       - If pull-request, the requester is the author.
    #     """

    def dispatch_on_mention(self, body, payload, user):
        """
        Core of the logic that let people require actions from the bot.

        Logic is relatively strait forward at the base,
        let `user` only trigger action it has sufficient permissions to do so.

        Typically an action can be done if you are at least:
            - owner
            - admin
            - have write permission
            - read permissions
            - no permission.

        It is a bit trickier in the following case.

            - You are a PR author (and owner of the branch you require to be merged)

              The bot should still let you do these actions

            - You request permission to multiple repo, agreed only if you have
              at least write permission to the other repo.

            - You are a maintainer and request access to a repo from which a PR
              is coming.

        """

        # to dispatch to commands
        installation_id = payload["installation"]["id"]
        org = payload["repository"]["owner"]["login"]
        repo = payload["repository"]["name"]
        pull_request = payload.get("issue", payload).get("pull_request")
        pr_author = None
        pr_origin_org_repo = None
        allow_edit_from_maintainer = None
        session = self.auth.session(installation_id)
        if pull_request:
            # The PR author _may_ not have access to origin branch
            pr_author = payload.get("issue", {"user": {"login": None}})["user"]["login"]
            pr = session.ghrequest("GET", pull_request["url"]).json()
            pr_origin_org_repo = pr["head"]["repo"]["full_name"]
            origin_repo_org = pr["head"]["user"]["login"]
            allow_edit_from_maintainer = pr["maintainer_can_modify"]

        # might want to just look at whether the commenter has permission over said branch.
        # you _may_ have multiple contributors to a PR.
        is_legitimate_author = (pr_author == user) and (pr_author == origin_repo_org)
        if is_legitimate_author:
            print(user, "is legitimate author of this PR, letting commands go through")

        permission_level = session._get_permission(org, repo, user)
        command_args = process_mentionning_comment(body, self.mention_bot_re)
        for (command, arguments) in command_args:
            print("    :: treating", command, arguments)
            keen.add_event(
                "dispatch",
                {
                    "mention": {
                        "user": user,
                        "organisation": org,
                        "repository": "{}/{}".format(org, repo),
                        "command": command,
                    }
                },
            )
            handler = self.actions.get(command.lower(), None)
            command = command.lower()

            def user_can(user, command, repo, org, session):
                """
                callback to test whether the current user has custom permission set on said repository.
                """
                try:
                    path = ".meeseeksdev.yml"
                    resp = session.ghrequest(
                        "GET",
                        f"https://api.github.com/repos/{org}/{repo}/contents/{path}",
                        raise_for_status=False,
                    )
                except Exception:
                    print(
                        red
                        + "An error occurred getting repository config file."
                        + normal
                    )
                    import traceback

                    traceback.print_exc()
                    return False, {}
                conf = {}
                if resp.status_code == 404:
                    print(yellow + "config file not found" + normal)
                elif resp.status_code != 200:
                    print(red + f"unknown status code {resp.status_code}" + normal)
                    resp.raise_for_status()
                else:
                    conf = yaml.safe_load(
                        base64.decodebytes(resp.json()["content"].encode())
                    )
                    print(
                        green
                        + f"should test if {user} can {command} on {repo}/{org}"
                        + normal
                    )
                    # print(green + json.dumps(conf, indent=2) + normal)

                if user in conf.get("blacklisted_users", []):
                    return False, {}

                user_section = conf.get("users", {}).get(user, {})

                custom_allowed_commands = user_section.get("can", [])

                print(f"Custom allowed command for {user} are", custom_allowed_commands)

                if command in custom_allowed_commands:
                    print(yellow + f"would allow {user} to {command}")
                    if "config" in user_section:
                        user_section_config = user_section.get("config", {})
                        if isinstance(user_section_config, list):
                            print("pop0 from user_config")
                            user_section_config = user_section_config[0]
                        local_config = user_section_config.get(command, None)
                        if local_config:
                            print("returning local_config", local_config)
                            return True, local_config
                    return True, {}

                everyone_section = conf.get("special", {}).get("everyone", {})
                everyone_allowed_commands = everyone_section.get("can", [])

                print("with everyone taken into account", everyone_allowed_commands)
                if command in everyone_allowed_commands:
                    print(yellow + f"would allow {user} (via everyone) to do {command}")
                    if "config" in everyone_section:
                        everyone_section_config = everyone_section.get("config", {})
                        if isinstance(everyone_section_config, list):
                            print("pop0 from user_config")
                            everyone_section_config = everyone_section_config[0]
                        local_config = everyone_section_config.get(command, None)
                        if local_config:
                            print("returning local_config", local_config)
                            return True, local_config
                    return True, {}

                print(yellow + f"would not allow {user} to {command}")
                return False, {}

            if handler:
                print("    :: testing who can use ", str(handler))
                per_repo_config_allows = None
                local_config = {}
                try:
                    per_repo_config_allows, local_config = user_can(
                        user, command, repo, org, session
                    )
                except Exception:
                    print(red + "error runnign user_can" + normal)
                    import traceback

                    traceback.print_exc()

                if (permission_level.value >= handler.scope.value) or (
                    is_legitimate_author
                    and getattr(handler, "let_author", False)
                    or per_repo_config_allows
                ):
                    print(
                        "    :: authorisation granted ",
                        handler.scope,
                        "custom_rule:",
                        per_repo_config_allows,
                        local_config,
                    )
                    is_gen = inspect.isgeneratorfunction(handler)
                    maybe_gen = handler(
                        session=session,
                        payload=payload,
                        arguments=arguments,
                        local_config=local_config,
                    )
                    if is_gen:
                        gen = YieldBreaker(maybe_gen)
                        for org_repo in gen:
                            torg, trepo = org_repo.split("/")
                            session_id = self.auth.idmap.get(org_repo)
                            if session_id:
                                target_session = self.auth.session(session_id)
                                # TODO, if PR, admin and request is on source repo, allows anyway.
                                # we may need to also check allow edit from maintainer and provide
                                # another decorator for safety.
                                # @access_original_branch.

                                if target_session.has_permission(
                                    torg, trepo, user, Permission.write
                                ) or (
                                    pr_origin_org_repo == org_repo
                                    and allow_edit_from_maintainer
                                ):
                                    gen.send(target_session)
                                else:
                                    gen.send(None)
                            else:
                                print("org/repo not found", org_repo, self.auth.idmap)
                                gen.send(None)
                else:
                    try:
                        comment_url = payload.get("issue", payload.get("pull_request"))[
                            "comments_url"
                        ]
                        user = payload["comment"]["user"]["login"]
                        session.post_comment(
                            comment_url,
                            f"Awww, sorry {user} you do not seem to be allowed to do that, please ask a repository maintainer.",
                        )
                    except Exception:
                        import traceback

                        traceback.print_exc()
                    print(
                        "I Cannot let you do that: requires",
                        handler.scope.value,
                        " you have",
                        permission_level.value,
                    )
            else:
                print("unnknown command", command)


class MeeseeksBox:
    def __init__(self, commands, config):

        keen.add_event("status", {"state": "starting"})
        self.commands = commands
        self.port = int(os.environ.get("PORT", 5000))
        self.application = None
        self.config = config
        self.auth = Authenticator(
            self.config.integration_id,
            self.config.key,
            self.config.personnal_account_token,
            self.config.personnal_account_name,
        )
        self.auth._build_auth_id_mapping()

    def sig_handler(self, sig, frame):
        print(yellow, "Caught signal: %s, Shutting down..." % sig, normal)
        keen.add_event("status", {"state": "stopping"})
        tornado.ioloop.IOLoop.instance().add_callback(self.shutdown)

    def shutdown(self):
        self.server.stop()

        io_loop = tornado.ioloop.IOLoop.instance()

        deadline = time.time() + 10

        def stop_loop():
            now = time.time()
            if now < deadline and (io_loop._callbacks or io_loop._timeouts):
                print(red, "delay stop...", normal)
                io_loop.add_timeout(now + 1, stop_loop)
            else:
                print(yellow, "stopping now...", normal)
                io_loop.stop()

        stop_loop()

    def start(self):
        self.application = tornado.web.Application(
            [
                (r"/", MainHandler),
                (
                    r"/webhook",
                    WebHookHandler,
                    {
                        "actions": self.commands,
                        "config": self.config,
                        "auth": self.auth,
                    },
                ),
            ]
        )

        self.server = tornado.httpserver.HTTPServer(self.application)

        self.server.listen(self.port)
        tornado.ioloop.IOLoop.instance().start()
