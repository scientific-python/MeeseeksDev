"""
Define a few commands
"""

from .meeseeksbox.utils import Session, fix_issue_body, fix_comment_body

from .meeseeksbox.scopes import admin, write, everyone

from textwrap import dedent


def _format_doc(function, name):
    if not function.__doc__:
        doc = "  "
    else:
        doc = function.__doc__.splitlines()
    first, other = doc[0], "\n".join(doc[1:])
    return "`@meeseeksdev {} {}` ({}) \n{}  ".format(name, first, function.scope, other)


def help_make(commands):

    data = "\n".join([_format_doc(v, k) for k, v in commands.items()])

    @everyone
    def help(*, session, payload, arguments):
        comment_url = payload["issue"]["comments_url"]
        session.post_comment(
            comment_url,
            dedent(
                """The following commands are available:\n\n{}
                """.format(
                    data
                )
            ),
        )

    return help


@write
def close(*, session, payload, arguments, local_config=None):
    session.ghrequest("PATCH", payload["issue"]["url"], json={"state": "closed"})


@write
def open(*, session, payload, arguments, local_config=None):
    session.ghrequest("PATCH", payload["issue"]["url"], json={"state": "open"})


@write
def migrate_issue_request(
    *, session: Session, payload: dict, arguments: str, local_config=None
):
    """[to] {org}/{repo} 

Need to be admin on target repo. Replicate all comments on target repo and close current on.
    """

    """Todo:

    - Works through pagination of comments
    - Works through pagination of labels

    Link to non-migrated labels.
    """
    if arguments.startswith("to "):
        arguments = arguments[3:]

    org_repo = arguments
    org, repo = arguments.split("/")

    target_session = yield org_repo
    if not target_session:
        session.post_comment(
            payload["issue"]["comments_url"],
            body="I'm afraid I can't do that. Maybe I need to be installed on target repository ?\n"
            "Click [here](https://github.com/integrations/meeseeksdev/installations/new) to do that.".format(
                botname="meeseeksdev"
            ),
        )
        return

    issue_title = payload["issue"]["title"]
    issue_body = payload["issue"]["body"]
    original_org = payload["organization"]["login"]
    original_repo = payload["repository"]["name"]
    original_poster = payload["issue"]["user"]["login"]
    original_number = payload["issue"]["number"]
    migration_requester = payload["comment"]["user"]["login"]
    request_id = payload["comment"]["id"]
    original_labels = [l["name"] for l in payload["issue"]["labels"]]

    if original_labels:
        available_labels = target_session.ghrequest(
            "GET",
            "https://api.github.com/repos/{org}/{repo}/labels".format(
                org=org, repo=repo
            ),
            None,
        ).json()

        available_labels = [l["name"] for l in available_labels]

    migrate_labels = [l for l in original_labels if l in available_labels]
    not_set_labels = [l for l in original_labels if l not in available_labels]

    new_response = target_session.create_issue(
        org,
        repo,
        issue_title,
        fix_issue_body(
            issue_body,
            original_poster,
            original_repo,
            original_org,
            original_number,
            migration_requester,
        ),
        labels=migrate_labels,
    )

    new_issue = new_response.json()
    new_comment_url = new_issue["comments_url"]

    original_comments = session.ghrequest(
        "GET", payload["issue"]["comments_url"], None
    ).json()

    for comment in original_comments:
        if comment["id"] == request_id:
            continue
        body = comment["body"]
        op = comment["user"]["login"]
        url = comment["html_url"]
        target_session.post_comment(
            new_comment_url,
            body=fix_comment_body(body, op, url, original_org, original_repo),
        )

    if not_set_labels:
        body = "I was not able to apply the following label(s): %s " % ",".join(
            not_set_labels
        )
        target_session.post_comment(new_comment_url, body=body)

    session.post_comment(
        payload["issue"]["comments_url"],
        body="Done as {}/{}#{}.".format(org, repo, new_issue["number"]),
    )
    session.ghrequest("PATCH", payload["issue"]["url"], json={"state": "closed"})


from .meeseeksbox.scopes import pr_author, write
from .meeseeksbox.commands import tag, untag


@pr_author
@write
def ready(*, session, payload, arguments, local_config=None):
    """{no arguments}

    Remove "waiting for author" tag, adds "need review" tag. Can also be issued
    if you are the current PR author even if you are not admin. 
    """
    tag(session, payload, "need review")
    untag(session, payload, "waiting for author")


@write
def merge(*, session, payload, arguments, method="merge", local_config=None):
    print("===== merging =====")
    if arguments:
        if arguments not in {"merge", "squash", "rebase"}:
            print("don't know how to merge with methods", arguments)
            return
        else:
            method = arguments
    prnumber = payload["issue"]["number"]
    org_name = payload["repository"]["owner"]["login"]
    repo_name = payload["repository"]["name"]

    # collect extended payload on the PR
    print("== Collecting data on Pull-request...")
    r = session.ghrequest(
        "GET",
        "https://api.github.com/repos/{}/{}/pulls/{}".format(
            org_name, repo_name, prnumber
        ),
        json=None,
    )
    pr_data = r.json()
    head_sha = pr_data["head"]["sha"]
    mergeable = pr_data["mergeable"]
    repo_name = pr_data["head"]["repo"]["name"]
    if mergeable:

        resp = session.ghrequest(
            "PUT",
            "https://api.github.com/repos/{}/{}/pulls/{}/merge".format(
                org_name, repo_name, prnumber
            ),
            json={"sha": head_sha, "merge_method": method},
            override_accept_header="application/vnd.github.polaris-preview+json",
        )
        print("------------")
        print(resp.json())
        print("------------")
        resp.raise_for_status()
    else:
        print("Not mergeable", pr_data["mergeable"])


###
# Lock and Unlock are not yet available for integration.
###
# def _lock_primitive(meth,*, session, payload, arguments):
#     number = payload['issue']['number']
#     org_name = payload['repository']['owner']['login']
#     repo_name = payload['repository']['name']
#     session.ghrequest('PUT', 'https://api.github.com/repos/{}/{}/issues/{}/lock'.format(org_name, repo_name, number))
#
# @admin
# def lock(**kwargs):
#     _lock_primitive('PUT', **kwargs)
#
# @admin
# def unlock(**kwargs):
#     _lock_primitive('DELETE', **kwargs)
