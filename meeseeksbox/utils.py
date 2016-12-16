"""
Utility functions to work with github.
"""
import jwt
import datetime
import json
import requests
import re
import subprocess
import git
import mock
import pipes
import os
import sys

API_COLLABORATORS_TEMPLATE = 'https://api.github.com/repos/{org}/{repo}/collaborators/{username}'

"""
Regular expression to relink issues/pr comments correctly.

Pay attention to not relink things like foo#23 as they already point to a
specific repository.
"""
RELINK_RE = re.compile('(?:(?<=[:,\s])|(?<=^))(#\d+)\\b')



def fix_issue_body(body, original_poster, original_repo, original_org, original_number, migration_requester):
    """
    This, for now does only simple fixes, like link to the original issue.
    
    This should be improved to quote mention of people
    """

    body = RELINK_RE.sub('{org}/{repo}\\1'.format(org=original_org, repo=original_repo), body)
    
    return body + \
    """\n\n---- 
    \nOriginally opened as {org}/{repo}#{number} by @{reporter}, migration requested by @{requester}
    """.format(org=original_org, repo=original_repo, number=original_number, reporter=original_poster,  requester=migration_requester)

def fix_comment_body(body, original_poster, original_url, original_org, original_repo):
    """
    This, for now does only simple fixes, like link to the original comment.
    
    This should be improved to quote mention of people
    """

    body = RELINK_RE.sub('{org}/{repo}\\1'.format(org=original_org, repo=original_repo), body)
    
    return """`@{op}` [commented]({original_url}):\n\n-----\n""".format(op=original_poster, original_url=original_url)+body



class Authenticator:
    
    def __init__(self, integration_id, rsadata):
        self.since = int(datetime.datetime.now().timestamp())
        self.duration = 60*10
        self._token = None
        self.integration_id = integration_id
        self.rsadata = rsadata

    def session(self, installation_id):
        return Session(self.integration_id, self.rsadata, installation_id)
        
    def list_installations(self):
        """
        Todo: Pagination
        """
        response = self._integration_authenticated_request(
            'GET', "https://api.github.com/integration/installations")
        response.raise_for_status()
        return response.json()

    def _build_auth_id_mapping(self):
        """
        Build an organisation/repo -> installation_id mappingg in order to be able
        to do cross repository operations.
        """

        installations = self.list_installations()
        import pprint
        for installation in installations:
            iid = installation['id']
            session = self.session(iid)
            repositories = session.ghrequest(
                'GET', installation['repositories_url'], json=None).json()
            pprint.pprint(repositories)

    def _integration_authenticated_request(self, method, url):
        self.since= int(datetime.datetime.now().timestamp())
        payload = dict({
          'iat': self.since,
          'exp': self.since + self.duration,
          'iss': self.integration_id,
        })

        tok = jwt.encode(payload, key=self.rsadata, algorithm='RS256')

        headers = {'Authorization': 'Bearer {}'.format(tok.decode()),
                   'Accept' : 'application/vnd.github.machine-man-preview+json' ,
                   'Host': 'api.github.com',
                   'User-Agent': 'python/requests'}
                   
        req = requests.Request(method, url, headers=headers)
        prepared = req.prepare()
        with requests.Session() as s:
            return s.send(prepared)
        

class Session(Authenticator):

    def __init__(self, integration_id, rsadata, installation_id):
        super().__init__(integration_id, rsadata)
        self.installation_id = installation_id

    def token(self):
        now = datetime.datetime.now().timestamp()
        if (now > self.since + self.duration-60) or (self._token is None):
            self.regen_token()
            
        return self._token
            
        
    def regen_token(self):
        method = 'GET'
        url = 'https://api.github.com/installations/%s/access_tokens'%self.installation_id
        resp = self._integration_authenticated_request(method, url)
        try:
            self._token = json.loads(resp.content.decode())['token']
        except:
            print(resp.content, url)

    
    def ghrequest(self, method, url, json):
        def prepare():
            atk = self.token()
            headers = {'Authorization': 'Bearer {}'.format(atk),
                       'Accept' : 'application/vnd.github.machine-man-preview+json' ,
                       'Host': 'api.github.com',
                       'User-Agent': 'python/requests'}
            req = requests.Request(method, url, headers=headers, json=json)
            return req.prepare()


        with requests.Session() as s:
            response = s.send(prepare())
            if response.status_code == 401:
                print("Not authorized", response.json)
                self.regen_token()
                response = s.send(prepare())
            response.raise_for_status()
            return response

    def is_collaborator(self, org, repo, username):
        """
        Check if a user is collaborator on this repository
        
        Right now this is a boolean, there is a new API
        (application/vnd.github.korra-preview) with github which allows to get
        finer grained decision.
        """
        get_collaborators_query = API_COLLABORATORS_TEMPLATE.format(org=org, repo=repo, username=username)
        resp = self.ghrequest('GET', get_collaborators_query, None)
        if resp.status_code == 204:
            return True
        elif resp.status_code == 404:
            return False
        else:
            resp.raise_for_status()

    def post_comment(self, comment_url, body):
        print('### Look at me posting comment')
        self.ghrequest('POST', comment_url, json={"body":body})

    def get_collaborator_list(self, org, repo):
        get_collaborators_query = 'https://api.github.com/repos/{org}/{repo}/collaborators'.format(org=org, repo=repo)
        resp = self.ghrequest('GET', get_collaborators_query, None)
        if resp.status_code == 200:
            return resp.json()
        else:
            resp.raise_for_status()


    def create_issue(self, org:str, repo:str , title:str, body:str, *, labels=None, assignees=None):
        arguments = {
            "title": title, 
            "body": body,
        }
        
        if labels:
            if type(labels) in (list, tuple):
                arguments['labels'] = labels
            else:
                raise ValueError('Labels must be a list of a tuple')
            
        if assignees:
            if type(assignees) in (list, tuple):
                arguments['assignees'] = assignees
            else:
                raise ValueError('Assignees must be a list or a tuple')
            
        return self.ghrequest('POST', 'https://api.github.com/repos/{}/{}/issues'.format(org, repo), 
                    json=arguments)

    def migrate_issue_request(self, data, org, repo):
        """Todo:

        - Works through pagination of comments
        - Works through pagination of labels

        Link to non-migrated labels.

        """



        issue_title = data['issue']['title']
        issue_body = data['issue']['body']
        original_org = data['organization']['login']
        original_repo = data['repository']['name']
        original_poster = data['issue']['user']['login']
        original_number = data['issue']['number']
        migration_requester = data['comment']['user']['login']
        request_id = data['comment']['id']
        original_labels =  [l['name'] for l in data['issue']['labels']]

        if original_labels:
            available_labels = self.ghrequest('GET', 
                    'https://api.github.com/repos/{org}/{repo}/labels'.format(org=org, repo=repo),
                    None).json()

            available_labels = [l['name'] for l in available_labels]

        migrate_labels = [l for l in original_labels if l in available_labels]
        not_set_labels = [l for l in original_labels if l not in available_labels]
        
        response = self.create_issue(org, repo , issue_title,
                            fix_issue_body(issue_body, original_poster, original_repo, original_org, original_number, migration_requester),
                            labels=migrate_labels
                            )
        
        new_issue = response.json()
        comment_url = new_issue['comments_url']
        
        original_comments = self.ghrequest('GET', data['issue']['comments_url'], None).json()
        
        for comment in original_comments:
            if comment['id'] == request_id:
                continue
            body = comment['body']
            op = comment['user']['login']
            url = comment['html_url']
            self.post_comment(comment_url, body=fix_comment_body(body, op, url, original_org, original_repo))

        if not_set_labels:
            body ="I was not able to apply the following label(s): %s " % ','.join( not_set_labels)
            self.post_comment(comment_url, body=body )


        self.post_comment(data['issue']['comments_url'], body='Done as {}/{}#{}.'.format(org, repo, new_issue['number']))
        self.ghrequest('PATCH', data['issue']['url'], json={'state':'closed'})

    def backport(self, target_branch, data):
        # collect initial data
        prnumber = data['issue']['number']
        prtitle  = data['issue']['title']
        org_name = data['organization']['login']
        repo_name = data['repository']['name']
        
        # collect extended data on the PR
        print('== Collecting data on Pull-request...')
        r = self.ghrequest('GET', 
            'https://api.github.com/repos/{}/{}/pulls/{}'.format(org_name, repo_name, prnumber),
            json=None)
        pr_data = r.json()
        merge_sha = pr_data['merge_commit_sha']
        body = pr_data['body']
        
        # clone locally
        # this process can take some time, regen token
        self.regen_token()
        atk = self.token()

        if os.path.exists(repo_name):
            print('== Cleaning up previsous work... ')
            subprocess.run('rm -rf {}'.format(repo_name).split(' '))
            print('== Done cleaning ')

        print('== Cloning current repository, this can take some time..')
        process = subprocess.run(['git', 'clone', 'https://x-access-token:{}@github.com/{}/{}'.format(atk, org_name, repo_name)])
        print('== Cloned..')
        process.check_returncode()

        subprocess.run('git config --global user.email ipy.bot@bot.com'.split(' '))
        subprocess.run('git config --global user.name FriendlyBot'.split(' '))

        # do the backport on local filesystem
        repo = git.Repo(repo_name)
        print('== Fetching branch to backport on ...')
        repo.remotes.origin.fetch('refs/heads/{}:workbranch'.format(target_branch))
        repo.git.checkout('workbranch')
        print('== Fetching Commits to backport...')
        repo.remotes.origin.fetch('{mergesha}'.format(num=prnumber, mergesha=merge_sha))
        print('== All has been fetched correctly')

        # remove mentions from description, to avoid pings:
        description = body.replace('@', ' ').replace('#', ' ')

        print("Cherry-picking %s" % merge_sha)
        args = ('-m', '1', merge_sha)

        try:
            with mock.patch.dict('os.environ', {'GIT_EDITOR': 'true'}):
                repo.git.cherry_pick(*args)
        except Exception as e:
            print('\n' + e.stderr.decode('utf8', 'replace'), file=sys.stderr)
            print('\n' + repo.git.status(), file=sys.stderr)
            cmd = ' '.join(pipes.quote(arg) for arg in sys.argv)
            print('\nPatch did not apply. Resolve conflicts (add, not commit), then re-run `%s`' % cmd, file=sys.stderr)

        # write the commit message
        msg = "Backport PR #%i: %s" % (prnumber, prtitle) + '\n\n' + description
        repo.git.commit('--amend', '-m', msg)

        print("== PR #%i applied, with msg:" % prnumber)
        print()
        print(msg)
        print("== ")

        # Push the backported work
        remote_submit_branch = 'auto-backport-of-pr-{}'.format(prnumber)
        print("== Pushing work....:")
        repo.remotes.origin.push('workbranch:{}'.format(remote_submit_branch))
        repo.git.checkout('master')
        repo.branches.workbranch.delete(repo, 'workbranch', force=True)
                                        
        
        # ToDO checkout master and get rid of branch
        
        # Make the PR on GitHub
        new_pr = self.ghrequest('POST', 'https://api.github.com/repos/{}/{}/pulls'.format(org_name, repo_name), json={
            "title": "Backport PR #%i on branch %s" % (prnumber, target_branch),
            "body": msg,
            "head": "{}:{}".format(org_name,remote_submit_branch),
            "base": target_branch
        })

        new_number = new_pr.json().get('number', None)
        print('Backported as PR', new_number)
        return new_pr.json()
