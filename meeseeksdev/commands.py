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

from .scopes import admin, everyone

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
    target_branch = arguments
    # collect initial payload
    prnumber = payload['issue']['number']
    prtitle = payload['issue']['title']
    org_name = payload['organization']['login']
    repo_name = payload['repository']['name']

    # collect extended payload on the PR
    print('== Collecting data on Pull-request...')
    r = session.ghrequest('GET',
                          'https://api.github.com/repos/{}/{}/pulls/{}'.format(
                              org_name, repo_name, prnumber),
                          json=None)
    pr_data = r.json()
    merge_sha = pr_data['merge_commit_sha']
    # body = pr_data['body']

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

    subprocess.run('git config --global user.email ipy.bot@bot.com'.split(' '))
    subprocess.run('git config --global user.name FriendlyBot'.split(' '))

    # do the backport on local filesystem
    repo = git.Repo(repo_name)
    print('== Fetching branch to backport on ...')
    repo.remotes.origin.fetch('refs/heads/{}:workbranch'.format(target_branch))
    repo.git.checkout('workbranch')
    print('== Fetching Commits to backport...')
    repo.remotes.origin.fetch('{mergesha}'.format(
        num=prnumber, mergesha=merge_sha))
    print('== All has been fetched correctly')

    # write the commit message
    msg = "Autofix pep 8 of #%i: %s" % (prnumber, prtitle) + '\n\n' 
    repo.git.commit('-m', msg)

    # Push the backported work
    remote_submit_branch = 'auto-backport-of-pr-{}'.format(prnumber)
    print("== Pushing work....:")
    repo.remotes.origin.push('workbranch:{}'.format(remote_submit_branch))
    repo.git.checkout('master')
    repo.branches.workbranch.delete(repo, 'workbranch', force=True)

    # ToDO checkout master and get rid of branch

    # Make the PR on GitHub
    new_pr = session.ghrequest('POST', 'https://api.github.com/repos/{}/{}/pulls'.format(org_name, repo_name), json={
        "title": "Backport PR #%i on branch %s" % (prnumber, target_branch),
        "body": msg,
        "head": "{}:{}".format(org_name, remote_submit_branch),
        "base": target_branch
    })

    new_number = new_pr.json().get('number', None)
    print('Backported as PR', new_number)
    return new_pr.json()
    

@admin
def backport(session, payload, arguments):
    target_branch = arguments
    # collect initial payload
    prnumber = payload['issue']['number']
    prtitle = payload['issue']['title']
    org_name = payload['organization']['login']
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

    subprocess.run('git config --global user.email ipy.bot@bot.com'.split(' '))
    subprocess.run('git config --global user.name FriendlyBot'.split(' '))

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

    try:
        with mock.patch.dict('os.environ', {'GIT_EDITOR': 'true'}):
            repo.git.cherry_pick(*args)
    except Exception as e:
        print('\n' + e.stderr.decode('utf8', 'replace'), file=sys.stderr)
        print('\n' + repo.git.status(), file=sys.stderr)
        cmd = ' '.join(pipes.quote(arg) for arg in sys.argv)
        print('\nPatch did not apply. Resolve conflicts (add, not commit), then re-run `%s`' %
              cmd, file=sys.stderr)

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
    new_pr = session.ghrequest('POST', 'https://api.github.com/repos/{}/{}/pulls'.format(org_name, repo_name), json={
        "title": "Backport PR #%i on branch %s" % (prnumber, target_branch),
        "body": msg,
        "head": "{}:{}".format(org_name, remote_submit_branch),
        "base": target_branch
    })

    new_number = new_pr.json().get('number', None)
    print('Backported as PR', new_number)
    return new_pr.json()


@admin
def tag(*, session, payload, arguments):
    org = payload['organization']['login']
    repo = payload['repository']['name']
    num = payload.get('issue').get('number')
    url = "https://api.github.com/repos/{org}/{repo}/issues/{num}/labels".format(**locals())
    tags = [arg.strip() for arg in arguments.split(',')]
    session.ghrequest('POST', url, json=tags)


@admin
def untag(*, session, payload, arguments):
    org = payload['organization']['login']
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

    issue_title = payload['issue']['title']
    issue_body = payload['issue']['body']
    original_org = payload['organization']['login']
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
