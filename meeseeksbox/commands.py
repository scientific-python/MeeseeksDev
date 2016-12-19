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

from .scopes import admin, everyone

@everyone
def replyuser(*, session, payload, arguments):
    print("I'm replying to a user, look at me.")
    comment_url     = payload['issue']['comments_url']
    user            = payload['issue']['user']['login']
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
    print('Posting the zen of Python triggered')
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
    print("I'm replying to an admin, look at me.")
    comment_url     = payload['issue']['comments_url']
    user            = payload['issue']['user']['login']
    session.post_comment(comment_url, "Hello @{user}. Waiting for your orders.".format(user=user))


@admin
def backport(session, payload, arguments):
    target_branch = arguments
    data = payload
    # collect initial data
    prnumber = data['issue']['number']
    prtitle = data['issue']['title']
    org_name = data['organization']['login']
    repo_name = data['repository']['name']

    # collect extended data on the PR
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
