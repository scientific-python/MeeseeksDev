import re
import os
import base64
import hmac
import tornado
import tornado.httpserver
import tornado.ioloop
import tornado.web

def load_config():
    """
    Load the configuration, for now stored in the environment
    """
    config={}


    ### Setup integration ID ###
    integration_id = os.environ.get('GITHUB_INTEGRATION_ID')
    if not integration_id:
        raise ValueError('Please set GITHUB_INTEGRATION_ID')

    integration_id = int(integration_id)
    config['integration_id'] = integration_id


    ### Setup bot name

    botname = os.environ.get('GITHUB_BOT_NAME', None)
    if not botname:
        raise ValueError('Need to set a botnames')

    if "@" in botname:
        print("Don't include @ in the botname !")

    botname = botname.replace('@','')
    at_botname = '@'+botname

    config['botname'] = botname
    config['at_botname'] = at_botname

    config['webhook_secret'] = os.environ.get('WEBHOOK_SECRET')

    config['key'] = base64.b64decode(bytes(os.environ.get('B64KEY'), 'ASCII'))

    return config

CONFIG = None 
AUTH = None

from .utils import Authenticator


### setup various regular expressions
# import re
# MIGRATE_RE = re.compile(re.escape(AT_BOTNAME)+'(?P<sudo> sudo)?(?: can you)? migrate (?:this )?to (?P<org>[a-z-]+)/(?P<repo>[a-z-]+)')
# BACKPORT_RE = re.compile(re.escape(AT_BOTNAME)+'(?: can you)? backport (?:this )?(?:on|to) ([\w.]+)')

### we need to setup this header
ACCEPT_HEADER = 'application/vnd.github.machine-man-preview+json'

### Private KEY


def verify_signature(payload, signature, secret):
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

# MIGRATE_RE = re.compile(re.escape(AT_BOTNAME)+'(?P<sudo> sudo)?(?: can you)? migrate (?:this )?to (?P<org>[a-z-]+)/(?P<repo>[a-z-]+)')
# BACKPORT_RE = re.compile(re.escape(AT_BOTNAME)+'(?: can you)? backport (?:this )?(?:on|to) ([\w.]+)')

def process_mentionning_comment(body, botname):
    """
    Given a comment body and a bot name parse this into a tuple of (command, arguments)
    """
    insensitive_bot_re = re.compile('@?'+re.escape(botname)+'(?:\[bot\])?', re.IGNORECASE)
    lines = body.splitlines()
    lines = [l.strip() for l in lines if insensitive_bot_re.search(l)]
    lines = [insensitive_bot_re.split(l)[-1].strip() for l in lines]
    
    command_args = [l.split(' ', 1) for l in lines]
    command_args = [c if len(c) > 1 else (c[0], None) for c in command_args]
    return command_args
    
    
class WebHookHandler(MainHandler):

    def initialize(self, actions, *args, **kwargs):
        self.actions = actions
        super().initialize(*args, **kwargs)
        print('Webhook initialize got', args, kwargs)

    def get(self):
        self.getfinish("Webhook alive and listening")

    def post(self):
        if not 'X-Hub-Signature' in self.request.headers:
            return self.error('WebHook not configured with secret')

        if not verify_signature(self.request.body,
                            self.request.headers['X-Hub-Signature'],
                            CONFIG['webhook_secret']):
            return self.error('Cannot validate GitHub payload with ' \
                                'provided WebHook secret')

        payload = tornado.escape.json_decode(self.request.body)
        action = payload.get("action", None)

        if action:
            print('## dispatching request', self.request.headers.get('X-GitHub-Delivery'))
            return self.dispatch_action(action, payload)
        else:
            print('No action available  for the webhook :', payload)

    def dispatch_action(self, type_, payload):
        botname = CONFIG['botname']
        ## new issue/PR opened
        if type_ == 'opened':
            issue = payload.get('issue', None)
            if not issue:
                print('request has no issue key:', payload)
                return self.error('Not really good, request has no issue')
            if issue:
                user = payload['issue']['user']['login']
                if user == CONFIG['botname'].lower()+'[bot]':
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
                if botname in body:

                    # to dispatch to commands
                    installation_id = payload['installation']['id']
                    org = payload['organization']['login']
                    repo = payload['repository']['name']
                    session = AUTH.session(installation_id)
                    is_admin = session.is_collaborator(org, repo, user)
                    command_args = process_mentionning_comment(body, botname)
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
                    pass
                else:
                    print('Was not mentioned', CONFIG['botname'], body, '|',user)
            elif installation and installation.get('account'):
                print('we got a new installation maybe ?!', payload)
                return self.finish()
            else:
                print('not handled', payload)
        else :
            print("can't deal with ", type_, "yet")


class MeeseeksBox:
    
    def __init__(self, commands):
        self.commands = commands
        self.port = int(os.environ.get('PORT', 5000))
        self.application = None
        
    def start(self):
        self.application = tornado.web.Application([
            (r"/", MainHandler),
            (r"/webhook", WebHookHandler, dict({'actions':self.commands}))
        ])
        
        tornado.httpserver.HTTPServer(self.application).listen(self.port)
        tornado.ioloop.IOLoop.instance().start()
        
from .commands import replyuser, zen

def main():
    print('====== (re) starting ======')
    global CONFIG, AUTH
    CONFIG = load_config()
    AUTH = Authenticator(CONFIG['integration_id'], CONFIG['key'])
    MeeseeksBox(commands={
        'hello': replyuser,
        'zen': zen
    }).start()

if __name__ == "__main__":
    main()
