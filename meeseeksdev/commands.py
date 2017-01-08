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

from .meeseeksbox.utils import Session, fix_issue_body, fix_comment_body

from .meeseeksbox.scopes import admin, everyone

@admin
def close(*, session, payload, arguments):
    session.ghrequest('PATCH', payload['issue']
                      ['url'], json={'state': 'closed'})


@admin
def open(*, session, payload, arguments):
    session.ghrequest('PATCH', payload['issue']['url'], json={'state': 'open'})

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
        session.post_comment(
            payload['issue']['comments_url'], body="I'm afraid I can't do that. Maybe I need to be installed on target repository ?\n"
            "Click [here](@meeseeksdev[bot] migrate to carreau/ipython) to do that.".format(botname='meeseeksdev')

        )
        return


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
