import re
import os
import base64
import hmac
import tornado
import tornado.httpserver
import tornado.ioloop
import tornado.web

ACCEPT_HEADER = 'application/vnd.github.machine-man-preview+json'

def load_config():
    """
    Load the configuration, for now stored in the environment
    """
    config={}

    integration_id = os.environ.get('GITHUB_INTEGRATION_ID')
    botname = os.environ.get('GITHUB_BOT_NAME', None)
    
    if not integration_id:
        raise ValueError('Please set GITHUB_INTEGRATION_ID')

    if not botname:
        raise ValueError('Need to set a botnames')
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

    return config

from .utils import Authenticator

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

    def initialize(self, actions, config, *args, **kwargs):
        self.actions = actions
        self.config = config
        
        super().initialize(*args, **kwargs)
        print('Webhook initialize got', args, kwargs)

    def get(self):
        self.getfinish("Webhook alive and listening")

    def post(self):
        if not 'X-Hub-Signature' in self.request.headers:
            return self.error('WebHook not configured with secret')

        if not verify_signature(self.request.body,
                            self.request.headers['X-Hub-Signature'],
                            self.config['webhook_secret']):
            return self.error('Cannot validate GitHub payload with ' \
                                'provided WebHook secret')

        payload = tornado.escape.json_decode(self.request.body)
        action = payload.get("action", None)

        if action:
            print('## dispatching request', self.request.headers.get('X-GitHub-Delivery'))
            return self.dispatch_action(action, payload)
        else:
            print('No action available  for the webhook :', payload)
        
    @property
    def mentioned_bot_re(self):
        return re.compile('@?'+re.escape(self.botname)+'(?:\[bot\])?', re.IGNORECASE)
        
        
    def dispatch_action(self, type_, payload):
        botname = self.config['botname']
        ## new issue/PR opened
        if type_ == 'opened':
            issue = payload.get('issue', None)
            if not issue:
                print('request has no issue key:', payload)
                return self.error('Not really good, request has no issue')
            if issue:
                user = payload['issue']['user']['login']
                if user == self.config['botname'].lower()+'[bot]':
                    return self.finish("Not responding to self")
            # todo dispatch on on-open

        ## new comment created
        elif type_ == 'created':
            comment = payload.get('comment', None)
            installation = payload.get('installation', None)
            if comment:
                user = payload['comment']['user']['login']
                if user == botname.lower()+'[bot]':
                    print('Not responding to self')
                    return self.finish("Not responding to self")
                if '[bot]' in user:
                    print('Not responding to another bot')
                    return self.finish("Not responding to another bot")
                body = payload['comment']['body']
                print('Got a comment', body)
                if self.mentioned_bot_re.findall(body):
                    self.dispatch_on_mention(body, payload, user)
                else:
                    print('Was not mentioned', self.config['botname'], body, '|',user)
            elif installation and installation.get('account'):
                print('we got a new installation maybe ?!', payload)
                return self.finish()
            else:
                print('not handled', payload)
        else :
            print("can't deal with ", type_, "yet")
            
    def dispatch_on_mention(self, body, payload, user):
        
        # to dispatch to commands
        installation_id = payload['installation']['id']
        org = payload['organization']['login']
        repo = payload['repository']['name']
        session = self.auth.session(installation_id)
        is_admin = session.is_collaborator(org, repo, user)
        command_args = process_mentionning_comment(body, self.mention_bot_re)
        for (command, arguments) in command_args:
            print("    :: treating", command, arguments)
            handler = self.actions.get(command, None)
            if handler:
                print("    :: testing who can use ", str(handler) )
                if ((handler.scope == 'admin') and is_admin) or (handler.scope == 'everyone'):
                    print("    :: authorisation granted ", handler.scope)
                    handler(session=session, payload=payload, arguments=arguments)
                else :
                    print('I Cannot let you do that')
            else:
                print('unnknown command', command)

import json

class MeeseeksBox:
    
    def __init__(self, commands, config):
        self.commands = commands
        self.port = int(os.environ.get('PORT', 5000))
        self.application = None
        self.config = config
        self.auth = Authenticator(self.config['integration_id'], self.config['key'])
        print("=====================================")
        print("==    current installations        ==")
        print(json.dumps(self.auth.list_installations(), indent=2))
        print("==                                 ==")
        print("=====================================")
        
    def start(self):
        self.application = tornado.web.Application([
            (r"/", MainHandler),
            (r"/webhook", WebHookHandler, {'actions':self.commands, 'config':self.config})
        ])

        tornado.httpserver.HTTPServer(self.application).listen(self.port)
        tornado.ioloop.IOLoop.instance().start()
        
from .commands import replyuser, zen

def main():
    print('====== (re) starting ======')
    config = load_config()
    MeeseeksBox(commands={
        'hello': replyuser,
        'zen': zen
    }, config=config).start()

if __name__ == "__main__":
    main()
