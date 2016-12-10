import os
import base64
import hmac
import tornado
import tornado.httpserver
import tornado.ioloop
import tornado.web
from .scopes import admin, everyone



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

    botname = os.environ.get('GITHUB_BOT_NAME', 'ipyn[bot]')

    if "@" in botname:
        print("Don't include @ in the botname !")

    botname = botname.replace('@','')
    at_botname = '@'+botname

    config['botname'] = botname
    config['at_botname'] = at_botname

    config['webhook_secret'] = os.environ.get('WEBHOOK_SECRET')

    config['key'] = base64.b64decode(bytes(os.environ.get('B64KEY'), 'ASCII'))

    return config

CONFIG = load_config()

from .utils import Authenticator

AUTH = Authenticator(CONFIG['integration_id'], CONFIG['key'])

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

import re
# MIGRATE_RE = re.compile(re.escape(AT_BOTNAME)+'(?P<sudo> sudo)?(?: can you)? migrate (?:this )?to (?P<org>[a-z-]+)/(?P<repo>[a-z-]+)')
# BACKPORT_RE = re.compile(re.escape(AT_BOTNAME)+'(?: can you)? backport (?:this )?(?:on|to) ([\w.]+)')

hello_re = re.compile(re.escape('hello '+CONFIG['at_botname']))

@everyone
def replyuser(session, payload):
    comment_url     = payload['issue']['comments_url']
    user            = payload['issue']['user']['login']
    session.post_comment(comment_url, "Hello @{user}.".format(user=user))

@admin
def replyadmin(session, payload):
    comment_url     = payload['issue']['comments_url']
    user            = payload['issue']['user']['login']
    session.post_comment(comment_url, "Hello @{user}. Waiting for your orders.".format(user=user))
    

 
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
            return self.dispatch_action(action, payload)
        else:
            print('No action available  for the webhook :', payload)

    def dispatch_action(self, type_, payload):

        ## new issue/PR opened
        if type_ == 'opened':
            issue = payload.get('issue', None)
            if not issue:
                print('request has no issue key:', payload)
                return self.error('Not really good, request has no issue')
            if issue:
                user = payload['issue']['user']['login']
                if user == CONFIG['botname']:
                    return self.finish("Not responding to self")
            # todo dispatch on on-open

        ## new comment created
        elif type_ == 'created':
            comment = payload.get('comment', None)
            installation = payload.get('installation', None)
            if comment:
                user = payload['comment']['user']['login'] 
                if user == CONFIG['botname']:
                    return self.finish("Not responding to self")
                body = payload['comment']['body']
                if CONFIG['botname'] in body:

                    # to dispatch to commands
                    installation_id = payload['installation']['id']
                    session = AUTH.session(installation_id)
                    for reg, handler in self.actions:
                        if reg.match(body):
                            handler(session, payload)
                        else:
                            print(body, 'did not match', reg)
                    pass
            if installation and installation.get('account'):
                print('we got a new installation maybe ?!', payload)
                return self.finish()
            else:
                print('not handled', payload)
        else :
            print("can't deal with ", type_, "yet")


def main():
    actions = (
            (hello_re, replyuser),
        )
        
       
    application = tornado.web.Application([
        (r"/", MainHandler),
        (r"/webhook", WebHookHandler, dict({'actions':actions}))
    ])

    port = int(os.environ.get('PORT', 5000))
    tornado.httpserver.HTTPServer(application).listen(port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
