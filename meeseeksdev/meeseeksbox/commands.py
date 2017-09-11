"""
Define a few commands
"""

import random
import os
import subprocess
import git
import pipes
import mock
import sys
#from friendlyautopep8 import run_on_cwd

from .utils import Session, fix_issue_body, fix_comment_body

from .scopes import admin, everyone, write

@everyone
def replyuser(*, session, payload, arguments):
    print("I'm replying to a user, look at me.")
    comment_url     = payload['issue']['comments_url']
    user = payload['comment']['user']['login']
    c = random.choice(
            ("Helloooo @{user}, I'm Mr. Meeseeks! Look at me!",
            "Look at me, @{user}, I'm Mr. Meeseeks! ",
            "I'm Mr. Meeseek, @{user}, Look at meee ! ",
            )
        )
    session.post_comment(comment_url, c.format(user=user))
    
from textwrap import dedent
    
@everyone
def zen(*, session, payload, arguments):
    comment_url     = payload['issue']['comments_url']
    session.post_comment(comment_url,
    dedent(
        """
        Zen of Pyton ([pep 20](https://www.python.org/dev/peps/pep-0020/))
        ```
        >>> import this
        Beautiful is better than ugly.
        Explicit is better than implicit.
        Simple is better than complex.
        Complex is better than complicated.
        Flat is better than nested.
        Sparse is better than dense.
        Readability counts.
        Special cases aren't special enough to break the rules.
        Although practicality beats purity.
        Errors should never pass silently.
        Unless explicitly silenced.
        In the face of ambiguity, refuse the temptation to guess.
        There should be one-- and preferably only one --obvious way to do it.
        Although that way may not be obvious at first unless you're Dutch.
        Now is better than never.
        Although never is often better than *right* now.
        If the implementation is hard to explain, it's a bad idea.
        If the implementation is easy to explain, it may be a good idea.
        Namespaces are one honking great idea -- let's do more of those!
        ```
        """
    ))
    

@admin
def replyadmin(*, session, payload, arguments):
    comment_url     = payload['issue']['comments_url']
    user            = payload['issue']['user']['login']
    session.post_comment(comment_url, "Hello @{user}. Waiting for your orders.".format(user=user))


@admin
def pep8ify(*, session, payload, arguments):
    print('===== pe8ifying =====')
    print(payload)
    print('===== ========= =====')
    # collect initial payload
    prnumber = payload['issue']['number']
    prtitle = payload['issue']['title']
    org_name = payload['repository']['owner']['login']
    repo_name = payload['repository']['name']


    # collect extended payload on the PR
    print('== Collecting data on Pull-request...')
    r = session.ghrequest('GET',
                          'https://api.github.com/repos/{}/{}/pulls/{}'.format(
                              org_name, repo_name, prnumber),
                          json=None)
    pr_data = r.json()
    head_sha = pr_data['head']['sha']
    base_sha = pr_data['base']['sha']
    branch = pr_data['head']['ref']
    author_login = pr_data['head']['repo']['owner']['login']
    repo_name = pr_data['head']['repo']['name']

    # that will likely fail, as if PR, we need to bypass the fact that the
    # requester has technically no access to commiter repo.
    target_session = yield '{}/{}'.format(author_login, repo_name)
    if not target_session:
        comment_url     = payload['issue']['comments_url']
        session.post_comment(comment_url, body="I'm afraid I can't do that. Maybe I need to be installed on target repository ?\n"
            "Click [here](https://github.com/integrations/meeseeksdev/installations/new) to do that.".format(botname='meeseeksdev')
        )
        return

    # clone locally
    # this process can take some time, regen token
    atk = target_session.token()

    if os.path.exists(repo_name):
        print('== Cleaning up previsous work... ')
        subprocess.run('rm -rf {}'.format(repo_name).split(' '))
        print('== Done cleaning ')

    print('== Cloning current repository, this can take some time..')
    process = subprocess.run(
        ['git', 'clone', 'https://x-access-token:{}@github.com/{}/{}'.format(atk, author_login, repo_name)])
    print('== Cloned..')
    process.check_returncode()

    subprocess.run(
        'git config --global user.email meeseeksbot@jupyter.org'.split(' '))
    subprocess.run('git config --global user.name FriendlyBot'.split(' '))

    # do the pep8ify on local filesystem
    repo = git.Repo(repo_name)
    print('== Fetching branch to pep8ify on ...')
    repo.remotes.origin.fetch('{}:workbranch'.format(branch))
    repo.git.checkout('workbranch')
    print('== Fetching Commits to pep8ify...')
    repo.remotes.origin.fetch('{head_sha}'.format(head_sha=head_sha))
    print('== All has been fetched correctly')

    os.chdir(repo_name)
    subprocess.run('pep8radius --in-place'.split(' ') + [base_sha])
    os.chdir('..')

    # write the commit message
    msg = "Autofix pep 8 of #%i: %s" % (prnumber, prtitle) + '\n\n'
    repo.git.commit('-am', msg)

    # Push the pep8ify work
    print("== Pushing work....:")
    repo.remotes.origin.push('workbranch:{}'.format(branch))
    repo.git.checkout('master')
    repo.branches.workbranch.delete(repo, 'workbranch', force=True)

    

@admin
def backport(session, payload, arguments):
    """[to] {branch}"""
    if arguments is None:
        arguments = ''
    target_branch = arguments
    if target_branch.startswith('to '):
        target_branch = target_branch[3:].strip()
    # collect initial payload
    if 'issue' not in payload:
        print('debug autobackport', payload)
    prnumber = payload.get('number', payload['issue']['number'])
    prtitle = payload.get('title', payload['issue']['title'])
    org_name = payload['repository']['owner']['login']
    repo_name = payload['repository']['name']

    # collect extended payload on the PR
    print('== Collecting data on Pull-request...')
    r = session.ghrequest('GET',
                          'https://api.github.com/repos/{}/{}/pulls/{}'.format(
                              org_name, repo_name, prnumber),
                          json=None)
    pr_data = r.json()
    merge_sha = pr_data['merge_commit_sha']
    body = pr_data['body']
    milestone_number = pr_data['milestone']['number']
    print('----------------------------------------')
    print('milestone data :', pr_data['milestone'])
    print('----------------------------------------')
    if not target_branch.strip():
        milestone_title = pr_data['milestone']['title']
        parts = milestone_title.split('.')
        parts[-1] = 'x'
        infered_target_branch = '.'.join(parts)
        print('inferring branch....', infered_target_branch)
        target_branch = infered_target_branch
        if org_name == 'matplotlib' and repo_name == 'matplotlib':
            target_branch = 'v'+target_branch

    if milestone_number:
        milestone_number = int(milestone_number)
    try:
        labels_names = [l['name'] for l in payload['issue']['labels']]
    except KeyError:
        print('Did not find labels|', pr_data)
        return

    # clone locally
    # this process can take some time, regen token
    atk = session.token()

    if os.path.exists(repo_name):
        print('== Cleaning up previsous work... ')
        subprocess.run('rm -rf {}'.format(repo_name).split(' '))
        print('== Done cleaning ')

    print('== Cloning current repository, this can take some time..')
    process = subprocess.run(
        ['git', 'clone', 'https://x-access-token:{}@github.com/{}/{}'.format(atk, org_name, repo_name)])
    print('== Cloned..')
    process.check_returncode()

    subprocess.run('git config --global user.email meeseeksdevbot@jupyter.org'.split(' '))
    subprocess.run('git config --global user.name MeeseeksDev[bot]'.split(' '))

    # do the backport on local filesystem
    repo = git.Repo(repo_name)
    print('== Fetching branch to backport on ...')
    repo.remotes.origin.fetch('refs/heads/{}:workbranch'.format(target_branch))
    repo.git.checkout('workbranch')
    print('== Fetching Commits to backport...')
    repo.remotes.origin.fetch('{mergesha}'.format(
        num=prnumber, mergesha=merge_sha))
    print('== All has been fetched correctly')

    # remove mentions from description, to avoid pings:
    description = body.replace('@', ' ').replace('#', ' ')

    print("Cherry-picking %s" % merge_sha)
    args = ('-m', '1', merge_sha)

    comment_url = payload.get('comments_url', payload['issue']['comments_url'])
    try:
        with mock.patch.dict('os.environ', {'GIT_EDITOR': 'true'}):
            repo.git.cherry_pick(*args)
    except git.GitCommandError as e:
        if ('git commit --allow-empty' in e.stderr) or ('git commit --allow-empty' in e.stdout):
            session.post_comment(comment_url,
                    "Can't Dooooo.... It seem like this is already backported (commit is empty)."
                    "I won't do anything. MrMeeseeks out.")
            print(e.stderr)
            print('----')
            print(e.stdout)
            print('----')
            return
        elif "after resolving the conflicts" in e.stderr:
            cmd = ' '.join(pipes.quote(arg) for arg in sys.argv)
            print('\nPatch did not apply. Resolve conflicts (add, not commit), then re-run `%s`' % cmd, file=sys.stderr)
            session.post_comment(comment_url,
                   "There seem to be a conflict, please backport manually")
            org = payload['repository']['owner']['login']
            repo = payload['repository']['name']
            num = payload.get('issue').get('number')
            url = "https://api.github.com/repos/{org}/{repo}/issues/{num}/labels".format(**locals())
            print('trying to apply still needs manual backport')
            reply = session.ghrequest('POST', url, json=["Still Needs Manual Backport"])
            print('Should be applied:', reply)
            return
        else:
            session.post_comment(comment_url,
                    "Oops, something went wrong applying the patch... Please have  a look at my logs.")
            print(e.stderr)
            print('----')
            print(e.stdout)
            print('----')
            return
    except Exception as e:
        session.post_comment(comment_url,
                    "Hum, I actually crashed, that should not have happened.")
        print('\n' + e.stderr.decode('utf8', 'replace'), file=sys.stderr)
        print('\n' + repo.git.status(), file=sys.stderr)
        
        


        return

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
    print('try to create PR with milestone', milestone_number, 'and labels', labels_names)
    new_pr = session.ghrequest('POST', 'https://api.github.com/repos/{}/{}/pulls'.format(org_name, repo_name), json={
        "title": "Backport PR #%i on branch %s" % (prnumber, target_branch),
        "body": msg,
        "head": "{}:{}".format(org_name, remote_submit_branch),
        "base": target_branch,
    }).json()

    new_number = new_pr['number']
    resp = session.ghrequest('PATCH', 'https://api.github.com/repos/{}/{}/issues/{}'.format(org_name, repo_name, new_number),
        json={
            "milestone": milestone_number,
            "labels": labels_names,
        })
    print(resp.json())
    resp.raise_for_status()

    print('Backported as PR', new_number)
    return new_pr

@admin
def tag(session, payload, arguments):
    "tag[, tag, [...] ]"
    org = payload['repository']['owner']['login']
    repo = payload['repository']['name']
    num = payload.get('issue').get('number')
    url = "https://api.github.com/repos/{org}/{repo}/issues/{num}/labels".format(**locals())
    tags = [arg.strip() for arg in arguments.split(',')]
    session.ghrequest('POST', url, json=tags)


@admin
def untag(session, payload, arguments):
    "tag[, tag, [...] ]"
    org = payload['repository']['owner']['login']
    repo = payload['repository']['name']
    num = payload.get('issue').get('number')
    tags = [arg.strip() for arg in arguments.split(',')]
    name = '{name}'
    url = "https://api.github.com/repos/{org}/{repo}/issues/{num}/labels/{name}".format(**locals())
    for tag in tags:
        session.ghrequest('DELETE', url.format(name=tag))

@admin
def migrate_issue_request(*, session:Session, payload:dict, arguments:str):
    """Todo:

    - Works through pagination of comments
    - Works through pagination of labels

    Link to non-migrated labels.
    """
    if arguments.startswith('to '):
        arguments = arguments[3:]

    org_repo = arguments
    org, repo = arguments.split('/')

    target_session = yield org_repo
    if not target_session:
        session.post_comment(payload['issue']['comments_url'], "It appears that I can't do that")
        return 

    issue_title = payload['issue']['title']
    issue_body = payload['issue']['body']
    original_org = payload['repository']['owner']['login']
    original_repo = payload['repository']['name']
    original_poster = payload['issue']['user']['login']
    original_number = payload['issue']['number']
    migration_requester = payload['comment']['user']['login']
    request_id = payload['comment']['id']
    original_labels = [l['name'] for l in payload['issue']['labels']]

    if original_labels:
        available_labels = target_session.ghrequest('GET',
                                                    'https://api.github.com/repos/{org}/{repo}/labels'.format(
                                                        org=org, repo=repo),
                                                    None).json()

        available_labels = [l['name'] for l in available_labels]

    migrate_labels = [l for l in original_labels if l in available_labels]
    not_set_labels = [l for l in original_labels if l not in available_labels]

    new_response = target_session.create_issue(org, repo, issue_title,
                                               fix_issue_body(
                                                   issue_body, original_poster, original_repo, original_org,
                                                   original_number, migration_requester),
                                               labels=migrate_labels
                                               )

    new_issue = new_response.json()
    new_comment_url = new_issue['comments_url']

    original_comments = session.ghrequest(
        'GET', payload['issue']['comments_url'], None).json()

    for comment in original_comments:
        if comment['id'] == request_id:
            continue
        body = comment['body']
        op = comment['user']['login']
        url = comment['html_url']
        target_session.post_comment(new_comment_url, body=fix_comment_body(
            body, op, url, original_org, original_repo))

    if not_set_labels:
        body = "I was not able to apply the following label(s): %s " % ','.join(
            not_set_labels)
        target_session.post_comment(new_comment_url, body=body)

    session.post_comment(payload['issue'][
                         'comments_url'], body='Done as {}/{}#{}.'.format(org, repo, new_issue['number']))
    session.ghrequest('PATCH', payload['issue'][
                      'url'], json={'state': 'closed'})


@write
def quote(*, session, payload, arguments):
    if arguments.lower() == 'over the world':
        comment_url     = payload['issue']['comments_url']
        user            = payload['issue']['user']['login']
    session.post_comment(comment_url, 
"""
> MeeseeksDev: Gee, {user}, what do you want to do tonight?
{user}: The same thing we do every night, MeeseeksDev - try to take over the world!
""".format(user=user))

