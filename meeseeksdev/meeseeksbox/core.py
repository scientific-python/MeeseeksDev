import re
import os
import hmac
import types
import tornado.web
import tornado.httpserver
import tornado.ioloop

from .utils import Authenticator
from .scopes import Permission

from yieldbreaker import YieldBreaker


class Config:
    botname = None
    integration_id = None
    key = None
    botname = None
    at_botname = None
    integration_id = None
    webhook_secret = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def validate(self):
        missing = [attr for attr in dir(self) if not attr.startswith(
            '_') and getattr(self, attr) is None]
        if missing:
            raise ValueError(
                'The followingg configuration options are missing : {}'.format(missing))
        return self


def verify_signature(payload, signature, secret):
    """
    Make sure hooks are encoded correctly
    """
    expected = 'sha1=' + hmac.new(secret.encode('ascii'),
                                  payload, 'sha1').hexdigest()
    return hmac.compare_digest(signature, expected)


class BaseHandler(tornado.web.RequestHandler):

    def error(self, message):
        self.set_status(500)
        self.write({'status': 'error', 'message': message})

    def success(self, message='', payload={}):
        self.write({'status': 'success', 'message': message, 'data': payload})


class MainHandler(BaseHandler):

    def get(self):
        self.finish('No')


def process_mentionning_comment(body, bot_re):
    """
    Given a comment body and a bot name parse this into a tuple of (command, arguments)
    """
    lines = body.splitlines()
    lines = [l.strip() for l in lines if bot_re.search(l)]
    lines = [bot_re.split(l)[-1].strip() for l in lines]

    command_args = [l.split(' ', 1) for l in lines]
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
        if not 'X-Hub-Signature' in self.request.headers:
            return self.error('WebHook not configured with secret')
        # TODO: Extract from X-GitHub-Event

        if not verify_signature(self.request.body,
                                self.request.headers['X-Hub-Signature'],
                                self.config.webhook_secret):
            return self.error('Cannot validate GitHub payload with '
                              'provided WebHook secret')

        payload = tornado.escape.json_decode(self.request.body)
        org = payload.get('repository', {}).get('owner', {}).get('login')
        if hasattr(self.config, 'org_whitelist') and (org not in self.config.org_whitelist):
            print('Non allowed org:', org)
            self.error('Not allowed org.')
        sender = payload.get('sender', {}).get('login', {})
        if hasattr(self.config, 'user_whitelist') and (sender not in self.config.user_whitelist):
            print('Not allowed user:', sender)
            self.error('Not allowed user.')


        action = payload.get("action", None)
        if payload.get('commits'):
            # TODO
            print("commits were likely pushed....")
            return

        if action:
            print('## dispatching request',
                  self.request.headers.get('X-GitHub-Delivery'))
            return self.dispatch_action(action, payload)
        else:
            event_type = self.request.headers.get('X-GitHub-Event')

            if event_type in {'status','fork','deployment_status', 'deployment'}:
                print('Not handeling event type', event_type,'yet.')
                return self.finish()

            print('No action available  for the webhook :',
                  self.request.headers.get('X-GitHub-Event'),  ':', payload)

    @property
    def mention_bot_re(self):
        botname = self.config.botname
        return re.compile('@?' + re.escape(botname) + '(?:\[bot\])?', re.IGNORECASE)

    def dispatch_action(self, type_, payload):
        botname = self.config.botname
        # new issue/PR opened
        if type_ == 'opened':
            issue = payload.get('issue', None)
            if not issue:
                print('request has no issue key:', payload)
                return self.error('Not really good, request has no issue')
            if issue:
                user = payload['issue']['user']['login']
                if user == self.config.botname.lower() + '[bot]':
                    return self.finish("Not responding to self")
            # todo dispatch on on-open

        elif type_ == 'added':
            installation = payload.get('installation', None)
            if installation and installation.get('account'):
                print('we got a new installation.')
                self.auth._build_auth_id_mapping()
                return self.finish()
            else:
                print("can't deal with this kind of payload yet", payload)
        # new comment created
        elif type_ == 'created':
            comment = payload.get('comment', None)
            installation = payload.get('installation', None)
            if comment:
                user = payload['comment']['user']['login']
                if user == botname.lower() + '[bot]':
                    print('Not responding to self')
                    return self.finish("Not responding to self")
                if '[bot]' in user:
                    print('Not responding to another bot')
                    return self.finish("Not responding to another bot")
                body = payload['comment']['body']
                print('Got a comment', body)
                if self.mention_bot_re.findall(body):
                    self.dispatch_on_mention(body, payload, user)
                else:
                    print('Was not mentioned',
                          self.config.botname, body, '|', user)
            elif installation and installation.get('account'):
                print('we got a new installation.')
                self.auth._build_auth_id_mapping()
                return self.finish()
            else:
                print('not handled', payload)
        else:
            print("can't deal with ", type_, "yet")

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
        let `user` only trigger action it has sufficient permissions to do.

        Typically an action can be done if you are at least:
            - owner
            - admin
            - have write permissin
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
        installation_id = payload['installation']['id']
        org = payload['organization']['login']
        repo = payload['repository']['name']
        pull_request = payload['issue'].get('pull_request')
        pr_author = None
        pr_origin_org_repo = None
        allow_edit_from_maintainer = None
        session = self.auth.session(installation_id)
        if pull_request:
            # The PR author _may_ not have access to origin branch
            pr_author = payload['issue']['user']['login']
            pr = session.ghrequest('GET', pull_request['url']).json()
            pr_origin_org_repo = pr['head']['repo']['full_name']
            origin_repo_org = pr['head']['user']['login']
            allow_edit_from_maintainer = pr['maintainer_can_modify']

        # might want to just look at whether the commenter has permission over said branch.
        # you _may_ have multiple contributors to a PR.
        is_legitimate_author = (pr_author == user) and (
            pr_author == origin_repo_org)

        permission_level = session._get_permission(org, repo, user)
        command_args = process_mentionning_comment(body, self.mention_bot_re)
        for (command, arguments) in command_args:
            print("    :: treating", command, arguments)
            handler = self.actions.get(command, None)
            if handler:
                print("    :: testing who can use ", str(handler))
                if (permission_level.value >= handler.scope.value) or \
                        (is_legitimate_author and getattr(handler, 'let_author')):
                    print("    :: authorisation granted ", handler.scope)
                    maybe_gen = handler(
                        session=session, payload=payload, arguments=arguments)
                    if type(maybe_gen) == types.GeneratorType:
                        gen = YieldBreaker(maybe_gen)
                        for org_repo in gen:
                            torg, trepo = org_repo.split('/')
                            session_id = self.auth.idmap.get(org_repo)
                            if session_id:
                                target_session = self.auth.session(session_id)
                                # TODO, if PR, admin and request is on source repo, allows anyway.
                                # we may need to also check allow edit from maintainer and provide
                                # another decorator for safety.
                                # @access_original_branch.
                                if target_session.has_permission(torg, trepo, user, Permission.write) or \
                                        (pr_origin_org_repo == org_repo and allow_edit_from_maintainer):
                                    gen.send(target_session)
                                else:
                                    gen.send(None)
                            else:
                                print('org/repo not found', org_repo, self.auth.idmap)
                                gen.send(None)
                else:
                    print('I Cannot let you do that: requires', handler.scope.value , ' you have', permission_level.value)
            else:
                print('unnknown command', command)


class MeeseeksBox:

    def __init__(self, commands, config):
        self.commands = commands
        self.port = int(os.environ.get('PORT', 5000))
        self.application = None
        self.config = config
        self.auth = Authenticator(self.config.integration_id, self.config.key)
        self.auth._build_auth_id_mapping()

    def start(self):
        self.application = tornado.web.Application([
            (r"/", MainHandler),
            (r"/webhook", WebHookHandler,
             {'actions': self.commands, 'config': self.config, 'auth': self.auth})
        ])

        tornado.httpserver.HTTPServer(self.application).listen(self.port)
        tornado.ioloop.IOLoop.instance().start()
