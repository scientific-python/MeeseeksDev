"""
Define a few commands
"""

import os
import pipes
import random
import re
import sys
import time
import traceback
from pathlib import Path
from textwrap import dedent
from typing import Generator, Optional
from unittest import mock

import git

from .scopes import admin, everyone, write
from .utils import Session, add_event, fix_comment_body, fix_issue_body, run

green = "\033[0;32m"
yellow = "\033[0;33m"
red = "\033[0;31m"
blue = "\x1b[0;34m"
normal = "\033[0m"


@everyone
def replyuser(*, session, payload, arguments, local_config=None):
    print("I'm replying to a user, look at me.")
    comment_url = payload["issue"]["comments_url"]
    user = payload["comment"]["user"]["login"]
    c = random.choice(
        (
            "Helloooo @{user}, I'm Mr. Meeseeks! Look at me!",
            "Look at me, @{user}, I'm Mr. Meeseeks! ",
            "I'm Mr. Meeseek, @{user}, Look at meee ! ",
        )
    )
    session.post_comment(comment_url, c.format(user=user))


@write
def say(*, session, payload, arguments, local_config=None):
    print("Oh, got local_config", local_config)
    comment_url = payload.get("issue", payload.get("pull_request"))["comments_url"]
    session.post_comment(comment_url, "".join(arguments))


@write
def debug(*, session, payload, arguments, local_config=None):
    print("DEBUG")
    print("session", session)
    print("payload", payload)
    print("arguments", arguments)
    print("local_config", local_config)


@everyone
def party(*, session, payload, arguments, local_config=None):
    comment_url = payload.get("issue", payload.get("pull_request"))["comments_url"]
    parrot = "![party parrot](http://cultofthepartyparrot.com/parrots/hd/parrot.gif)"
    session.post_comment(comment_url, parrot * 10)


@everyone
def zen(*, session, payload, arguments, local_config=None):
    comment_url = payload.get("issue", payload.get("pull_request"))["comments_url"]
    session.post_comment(
        comment_url,
        dedent(
            """
        Zen of Python ([pep 20](https://www.python.org/dev/peps/pep-0020/))
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
        ),
    )


@admin
def replyadmin(*, session, payload, arguments, local_config=None):
    comment_url = payload["issue"]["comments_url"]
    user = payload["issue"]["user"]["login"]
    session.post_comment(comment_url, f"Hello @{user}. Waiting for your orders.")


def _compute_pwd_changes(allowlist):
    import glob
    from difflib import SequenceMatcher

    import black

    post_changes = []
    import os

    print("== pwd", os.getcwd())
    print("== listdir", os.listdir())

    for path in glob.glob("**/*.py", recursive=True):
        print("=== scanning", path, path in allowlist)
        if path not in allowlist:
            # we don't touch files not in this PR.
            continue
        p = Path(path)
        old = p.read_text()
        new = black.format_str(old, mode=black.FileMode())
        if new != old:
            print("will differ")
            nl = new.splitlines()
            ol = old.splitlines()
            s = SequenceMatcher(None, ol, nl)
            for t, a1, a2, b1, b2 in s.get_opcodes():
                if t == "replace":

                    c = "```suggestion\n"

                    for n in nl[b1:b2]:
                        c += n
                        c += "\n"
                    c += "```"
                    ch = (p.as_posix(), a1, a2, c)
                    post_changes.append(ch)
    return post_changes


@admin
def black_suggest(*, session, payload, arguments, local_config=None):
    print("===== reformatting suggestions. =====")

    prnumber = payload["issue"]["number"]
    # prtitle = payload["issue"]["title"]
    org_name = payload["repository"]["owner"]["login"]
    repo_name = payload["repository"]["name"]

    # collect extended payload on the PR
    print("== Collecting data on Pull-request...")
    r = session.ghrequest(
        "GET",
        f"https://api.github.com/repos/{org_name}/{repo_name}/pulls/{prnumber}",
        json=None,
    )
    pr_data = r.json()
    head_sha = pr_data["head"]["sha"]
    # base_sha = pr_data["base"]["sha"]
    # branch = pr_data["head"]["ref"]
    # author_login = pr_data["head"]["repo"]["owner"]["login"]
    repo_name = pr_data["head"]["repo"]["name"]

    # commits_url = pr_data["commits_url"]

    # commits_data = session.ghrequest("GET", commits_url).json()

    # that will likely fail, as if PR, we need to bypass the fact that the
    # requester has technically no access to committer repo.
    # TODO, check if maintainer
    ## target_session = yield "{}/{}".format(author_login, repo_name)
    ## if target_session:
    ##     print('installed on target repository')
    ##     atk = target_session.token()
    ## else:
    ##     print('use allow edit as maintainer')
    ##     atk = session.token()
    ##     comment_url = payload["issue"]["comments_url"]
    ##     session.post_comment(
    ##         comment_url,
    ##         body="Would you mind installing me on your fork so that I can update your branch? \n"
    ##         "Click [here](https://github.com/apps/meeseeksdev/installations/new)"
    ##         "to do that, and follow the instructions to add your fork."
    ##         "I'm going to try to push as a maintainer but this may not work."
    ##     )
    # if not target_session:
    #     comment_url = payload["issue"]["comments_url"]
    #     session.post_comment(
    #         comment_url,
    #         body="I'm afraid I can't do that. Maybe I need to be installed on target repository?\n"
    #         "Click [here](https://github.com/apps/meeseeksdev/installations/new) to do that.".format(
    #             botname="meeseeksdev"
    #         ),
    #     )
    #     return

    # clone locally
    # this process can take some time, regen token

    # paginated by 30 files, let's nto go that far (yet)
    files_response = session.ghrequest(
        "GET",
        f"https://api.github.com/repos/{org_name}/{repo_name}/pulls/{prnumber}/files",
    )
    pr_files = [r["filename"] for r in files_response.json()]
    print("== PR contains", len(pr_files), "files")

    if os.path.exists(repo_name):
        print("== Cleaning up previous work ... ")
        run(f"rm -rf {repo_name}")
        print("== Done cleaning ")

    print(f"== Cloning repository from {org_name}/{repo_name}, this can take some time ...")
    process = run(
        [
            "git",
            "clone",
            "https://x-access-token:{}@github.com/{}/{}".format(
                session.token(), org_name, repo_name
            ),
        ]
    )
    print("== Cloned..")
    process.check_returncode()

    run("git config --global user.email meeseeksmachine@gmail.com")
    run("git config --global user.name FriendlyBot")

    # do the pep8ify on local filesystem
    repo = git.Repo(repo_name)
    # branch = master
    # print(f"== Fetching branch `{branch}` ...")
    # repo.remotes.origin.fetch("{}:workbranch".format(branch))
    # repo.git.checkout("workbranch")
    print("== Fetching Commits to reformat ...")
    repo.remotes.origin.fetch(f"{head_sha}")
    print("== All have been fetched correctly")
    repo.git.checkout(head_sha)
    print(f"== checked PR head {head_sha}")

    print("== Computing changes....")
    os.chdir(repo_name)
    changes = _compute_pwd_changes(pr_files)
    os.chdir("..")
    print("... computed", len(changes), changes)

    COMFORT_FADE = "application/vnd.github.comfort-fade-preview+json"
    # comment_url = payload["issue"]["comments_url"]
    # session.post_comment(
    #     comment_url,
    #     body=dedent("""
    #     I've rebased this Pull Request, applied `black` on all the
    #     individual commits, and pushed. You may have trouble pushing further
    #     commits, but feel free to force push and ask me to reformat again.
    #     """)
    # )

    for path, start, end, body in changes:
        print(f"== will suggest the following on {path} {start+1} to {end}\n", body)
        if start + 1 != end:
            data = {
                "body": body,
                "commit_id": head_sha,
                "path": path,
                "start_line": start + 1,
                "start_side": "RIGHT",
                "line": end,
                "side": "RIGHT",
            }

            try:
                _ = session.ghrequest(
                    "POST",
                    f"https://api.github.com/repos/{org_name}/{repo_name}/pulls/{prnumber}/comments",
                    json=data,
                    override_accept_header=COMFORT_FADE,
                )
            except Exception:
                # likely unprecessable entity out of range
                pass
        else:
            # we can't seem to do single line with COMFORT_FADE
            data = {
                "body": body,
                "commit_id": head_sha,
                "path": path,
                "line": end,
                "side": "RIGHT",
            }

            try:
                _ = session.ghrequest(
                    "POST",
                    f"https://api.github.com/repos/{org_name}/{repo_name}/pulls/{prnumber}/comments",
                    json=data,
                )
            except Exception:
                # likely unprocessable entity out of range
                pass
    if os.path.exists(repo_name):
        print("== Cleaning up repo... ")
        run(f"rm -rf {repo_name}")
        print("== Done cleaning ")


def prep_for_command(
    name: str,
    session: Session,
    payload: dict,
    arguments: str,
    local_config: Optional[dict] = None,
) -> Generator:
    """Prepare to run a command against a local checkout of a repo."""
    print(f"===== running command {name} =====")
    print("===== ============ =====")
    # collect initial payload
    # https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads#issue_comment
    prnumber = payload["issue"]["number"]
    org_name = payload["repository"]["owner"]["login"]
    repo_name = payload["repository"]["name"]
    comment_url = payload["issue"]["comments_url"]

    # collect extended payload on the PR
    # https://docs.github.com/en/rest/reference/pulls#get-a-pull-request
    print("== Collecting data on Pull-request...")
    r = session.ghrequest(
        "GET",
        f"https://api.github.com/repos/{org_name}/{repo_name}/pulls/{prnumber}",
        json=None,
    )
    pr_data = r.json()
    head_sha = pr_data["head"]["sha"]
    branch = pr_data["head"]["ref"]
    author_login = pr_data["head"]["repo"]["owner"]["login"]
    repo_name = pr_data["head"]["repo"]["name"]
    maintainer_can_modify = pr_data["maintainer_can_modify"]

    # Check to see if we can successfully push changees to the PR.
    target_session = yield f"{author_login}/{repo_name}"

    if target_session:
        print("installed on target repository")
        atk = target_session.token()
        session.post_comment(comment_url, body=f"Running {name} on this Pull Request...")
    else:
        print("use allow edit as maintainer")
        if maintainer_can_modify:
            msg = "For now I will push as a maintainer since it is enabled."
        else:
            msg = 'I would push as a maintainer but I cannot unless "Allow edits from maintainers" is enabled for this Pull Request.'
        atk = session.token()
        session.post_comment(
            comment_url,
            body=f"@{author_login}, would you mind installing me on your fork so that I can update your branch?\n"
            "Click [here](https://github.com/apps/meeseeksdev/installations/new) "
            "to do that, and follow the instructions to add your fork.\n\n"
            f"{msg}",
        )
        if not maintainer_can_modify:
            print("=== Bailing since we do not have permissions")
            return

    if os.path.exists(repo_name):
        print("== Cleaning up previous work ... ")
        run(f"rm -rf {repo_name}", check=True)
        print("== Done cleaning ")

    print(f"== Cloning repository from {author_login}/{repo_name}, this can take some time ...")
    process = run(
        [
            "git",
            "clone",
            f"https://x-access-token:{atk}@github.com/{author_login}/{repo_name}",
        ]
    )
    print("== Cloned..")
    process.check_returncode()

    run("git config --global user.email meeseeksmachine@gmail.com")
    run("git config --global user.name FriendlyBot")

    # do the command on local filesystem
    repo = git.Repo(repo_name)
    print(f"== Fetching branch `{branch}` to run {name} on ...")
    repo.remotes.origin.fetch(f"{branch}:workbranch")
    repo.git.checkout("workbranch")
    print(f"== Fetching Commits to run {name} on ...")
    repo.remotes.origin.fetch(f"{head_sha}")
    print("== All have been fetched correctly")

    os.chdir(repo_name)


def push_the_work(session, payload, arguments, local_config=None):
    """Push the work down in a local repo to the remote repo."""
    prnumber = payload["issue"]["number"]
    org_name = payload["repository"]["owner"]["login"]
    repo_name = payload["repository"]["name"]

    # collect extended payload on the PR
    print("== Collecting data on Pull-request...")
    r = session.ghrequest(
        "GET",
        f"https://api.github.com/repos/{org_name}/{repo_name}/pulls/{prnumber}",
        json=None,
    )
    pr_data = r.json()
    branch = pr_data["head"]["ref"]
    repo_name = pr_data["head"]["repo"]["name"]

    # Open the repo in the cwd
    repo = git.Repo(".")

    # Push the work
    print("== Pushing work....:")
    print(f"pushing with workbranch:{branch}")
    succeeded = True
    try:
        repo.remotes.origin.push(f"workbranch:{branch}", force=True).raise_if_error()
    except Exception:
        succeeded = False

    # Clean up
    default_branch = session.ghrequest(
        "GET", f"https://api.github.com/repos/{org_name}/{repo_name}"
    ).json()["default_branch"]
    repo.git.checkout(default_branch)
    repo.branches.workbranch.delete(repo, "workbranch", force=True)
    return succeeded


@admin
def precommit(
    *,
    session: Session,
    payload: dict,
    arguments: str,
    local_config: Optional[dict] = None,
) -> Generator:
    comment_url = payload["issue"]["comments_url"]

    """Run pre-commit against a PR and push the changes."""
    yield from prep_for_command("precommit", session, payload, arguments, local_config=local_config)

    # Make sure there is a pre-commit file.
    config = Path("./.pre-commit-config.yaml")
    if not config.exists():
        # Alert the caller and bail.
        session.post_comment(
            comment_url,
            body=dedent(
                """
            I was unable to fix pre-commit errors because there is no
            ".pre-commit-config.yaml" file.
            """
            ),
        )
        return

    # Install the package in editable mode if there are local hooks.
    if "repo: local" in config.read_text():
        run("pip install --user -e .")

    cmd = "pre-commit run --all-files --hook-stage=manual"

    # Run the command
    process = run(cmd)

    # See if the pre-commit succeeded, meaning there was nothing to do
    if process.returncode == 0:

        # Alert the caller and bail.
        session.post_comment(
            comment_url,
            body=dedent(
                """
            I was unable to run "pre-commit" because there was nothing to do.
            """
            ),
        )
        return

    # Add any changed files.
    process = run('git commit -a -m "Apply pre-commit"')
    made_changes = process.returncode == 0

    # Run again to see if we've auto-fixed
    process = run(cmd)

    # If second run fails, then we can't auto-fix
    if process.returncode != 0:

        if not made_changes:
            # Alert the caller and bail.
            session.post_comment(
                comment_url,
                body=dedent(
                    """
                I was unable to fix pre-commit errors automatically.
                Try running `pre-commit run --all-files` locally.
                """
                ),
            )
            return

        session.post_comment(
            comment_url,
            body=dedent(
                """
                I was unable to fix all of the pre-commit errors automatically.  Try running `pre-commit run --all-files` locally.
                """
            ),
        )

    succeeded = push_the_work(session, payload, arguments, local_config=local_config)

    # Tell the caller we've finished
    comment_url = payload["issue"]["comments_url"]
    if succeeded:
        session.post_comment(
            comment_url,
            body=dedent(
                """
            I've applied "pre-commit" and pushed. You may have trouble pushing further
            commits, but feel free to force push and ask me to run again.
            """
            ),
        )
    else:
        session.post_comment(comment_url, body="I was unable to push due to errors")


@admin
def blackify(*, session, payload, arguments, local_config=None):
    """Run black against all commits of on a PR and push the new commits."""
    yield from prep_for_command("blackify", session, payload, arguments, local_config=local_config)

    comment_url = payload["issue"]["comments_url"]

    prnumber = payload["issue"]["number"]
    org_name = payload["repository"]["owner"]["login"]
    repo_name = payload["repository"]["name"]

    r = session.ghrequest(
        "GET",
        f"https://api.github.com/repos/{org_name}/{repo_name}/pulls/{prnumber}",
        json=None,
    )
    pr_data = r.json()
    commits_url = pr_data["commits_url"]
    commits_data = session.ghrequest("GET", commits_url).json()

    for commit in commits_data:
        if len(commit["parents"]) != 1:
            session.post_comment(
                comment_url,
                body="It looks like the history is not linear in this pull-request. I'm afraid I can't rebase.\n",
            )
            return

    # so far we assume that the commit we rebase on is the first.
    to_rebase_on = commits_data[0]["parents"][0]["sha"]

    process = run(
        [
            "git",
            "rebase",
            "-x",
            "black --fast . && git commit -a --amend --no-edit",
            "--strategy-option=theirs",
            "--autosquash",
            to_rebase_on,
        ]
    )

    if process.returncode != 0:
        session.post_comment(
            comment_url,
            body=dedent(
                """
            I was unable to run "blackify" due to an error.
            """
            ),
        )
        return

    succeeded = push_the_work(session, payload, arguments, local_config=local_config)

    # Tell the caller we've finished
    if succeeded:
        session.post_comment(
            comment_url,
            body=dedent(
                """
            I've rebased this Pull Request, applied `black` on all the
            individual commits, and pushed. You may have trouble pushing further
            commits, but feel free to force push and ask me to reformat again.
            """
            ),
        )
    else:
        session.post_comment(comment_url, body="I was unable to push due to errors")


@write
def safe_backport(session, payload, arguments, local_config=None):
    """[to] {branch}"""
    import builtins

    print = lambda *args, **kwargs: builtins.print("    [backport]", *args, **kwargs)

    s_clone_time = 0.0
    s_success = False
    s_reason = "unknown"
    s_fork_time = 0.0
    s_clean_time = 0.0
    s_ff_time = 0.0
    s_slug = ""

    def keen_stats():
        nonlocal s_slug
        nonlocal s_clone_time
        nonlocal s_success
        nonlocal s_reason
        nonlocal s_fork_time
        nonlocal s_clean_time
        nonlocal s_ff_time
        add_event(
            "backport_stats",
            {
                "slug": s_slug,
                "clone_time": s_clone_time,
                "fork_time": s_fork_time,
                "clean_time": s_clean_time,
                "success": s_success,
                "fast_forward_opt_time": s_ff_time,
                "reason": s_reason,
            },
        )

    if arguments is None:
        arguments = ""
    target_branch = arguments
    if target_branch.startswith("to "):
        target_branch = target_branch[3:].strip()
    # collect initial payload
    if "issue" not in payload:
        print(
            green
            + 'debug safe_autobackport, "issue" not in payload, likely trigerd by milisetone merge.'
            + normal
        )
    prnumber = payload.get("issue", payload).get("number")
    prtitle = payload.get("issue", payload.get("pull_request", {})).get("title")
    org_name = payload["repository"]["owner"]["login"]
    repo_name = payload["repository"]["name"]
    comment_url = payload.get("issue", payload.get("pull_request"))["comments_url"]
    maybe_wrong_named_branch = False
    s_slug = f"{org_name}/{repo_name}"
    try:
        default_branch = session.ghrequest(
            "GET", f"https://api.github.com/repos/{org_name}/{repo_name}"
        ).json()["default_branch"]
        existing_branches = session.ghrequest(
            "GET", f"https://api.github.com/repos/{org_name}/{repo_name}/branches"
        ).json()
        existing_branches_names = {b["name"] for b in existing_branches}
        if target_branch not in existing_branches_names and target_branch.endswith("."):
            target_branch = target_branch[:-1]

        if target_branch not in existing_branches_names:
            print(
                red
                + f"Request to backport to `{target_branch}`, which does not seem to exist. Known : {existing_branches_names}"
            )
            maybe_wrong_named_branch = True
        else:
            print(green + f"found branch {target_branch}")
    except Exception:
        import traceback

        traceback.print_exc()
        s_reason = "Exception line 256"
        keen_stats()
    try:

        # collect extended payload on the PR
        print("== Collecting data on Pull-request ...")
        r = session.ghrequest(
            "GET",
            f"https://api.github.com/repos/{org_name}/{repo_name}/pulls/{prnumber}",
            json=None,
        )
        pr_data = r.json()
        merge_sha = pr_data["merge_commit_sha"]
        milestone = pr_data["milestone"]
        if milestone:
            milestone_number = pr_data["milestone"].get("number", None)
        else:
            milestone_number = None

        print("----------------------------------------")
        # print('milestone data :', pr_data['milestone'])
        print("----------------------------------------")
        if not target_branch.strip():
            milestone_title = pr_data["milestone"]["title"]
            parts = milestone_title.split(".")
            parts[-1] = "x"
            infered_target_branch = ".".join(parts)
            print("inferring branch ...", infered_target_branch)
            target_branch = infered_target_branch
            add_event("backport_infering_branch", {"infering_remove_x": 1})

        if milestone_number:
            milestone_number = int(milestone_number)
        labels_names = []
        try:
            labels_names = [
                l["name"] for l in pr_data["labels"] if l["name"] != "Still Needs Manual Backport"
            ]
            if not labels_names and ("issue" in payload.keys()):
                labels_names = [
                    l["name"]
                    for l in payload["issue"]["labels"]
                    if l["name"] != "Still Needs Manual Backport"
                ]
        except KeyError:
            print("Did not find labels|", pr_data)
        # clone locally
        # this process can take some time, regen token
        atk = session.token()

        # FORK it.
        fork_epoch = time.time()
        frk = session.personal_request(
            "POST", f"https://api.github.com/repos/{org_name}/{repo_name}/forks"
        ).json()

        for i in range(5):
            ff = session.personal_request("GET", frk["url"], raise_for_status=False)
            if ff.status_code == 200:
                add_event("fork_wait", {"n": i})
                break
            time.sleep(1)
        s_fork_time = time.time() - fork_epoch

        ## optimize-fetch-experiment
        print("Attempting FF")
        if os.path.exists(repo_name):
            try:
                re_fetch_epoch = time.time()
                run(
                    [
                        "git",
                        "remote",
                        "set-url",
                        "origin",
                        f"https://x-access-token:{atk}@github.com/{org_name}/{repo_name}",
                    ],
                    cwd=repo_name,
                ).check_returncode()

                repo = git.Repo(repo_name)
                print(f"FF: Git fetch {default_branch}")
                repo.remotes.origin.fetch(default_branch)
                repo.git.checkout(default_branch)
                run(
                    ["git", "reset", "--hard", f"origin/{default_branch}"],
                    cwd=repo_name,
                ).check_returncode()
                run(["git", "describe", "--tag"], cwd=repo_name)
                re_fetch_delta = time.time() - re_fetch_epoch
                print(blue + f"FF took {re_fetch_delta}s")
                s_ff_time = re_fetch_delta
            except Exception:
                # something went wrong. Kill repository it's going to be
                # recloned.
                clean_epoch = time.time()
                if os.path.exists(repo_name):
                    print("== Cleaning up previous work... ")
                    run(f"rm -rf {repo_name}")
                    print("== Done cleaning ")
                s_clean_time = time.time() - clean_epoch
                import traceback

                traceback.print_exc()
        ## end optimise-fetch-experiment

        clone_epoch = time.time()
        action = "set-url"
        what_was_done = "Fast-Forwarded"
        if not os.path.exists(repo_name):
            print("== Cloning current repository, this can take some time..")
            process = run(
                [
                    "git",
                    "clone",
                    f"https://x-access-token:{atk}@github.com/{org_name}/{repo_name}",
                ]
            )
            process.check_returncode()
            action = "add"
            what_was_done = "Cloned"

        s_clone_time = time.time() - clone_epoch

        process = run(
            [
                "git",
                "remote",
                action,
                session.personal_account_name,
                f"https://x-access-token:{session.personal_account_token}@github.com/{session.personal_account_name}/{repo_name}",
            ],
            cwd=repo_name,
        )
        print("==", what_was_done)
        process.check_returncode()

        run("git config --global user.email meeseeksmachine@gmail.com")
        run("git config --global user.name MeeseeksDev[bot]")

        # do the backport on local filesystem
        repo = git.Repo(repo_name)
        print(f"== Fetching branch to backport on ... {target_branch}")
        repo.remotes.origin.fetch(f"refs/heads/{target_branch}:workbranch")
        repo.git.checkout("workbranch")
        print(f"== Fetching Commits to {merge_sha} backport...")
        repo.remotes.origin.fetch(f"{merge_sha}")
        print("== All has been fetched correctly")

        print("Cherry-picking %s" % merge_sha)
        args: tuple = ("-x", "-m", "1", merge_sha)

        msg = "Backport PR #%i: %s" % (prnumber, prtitle)
        remote_submit_branch = f"auto-backport-of-pr-{prnumber}-on-{target_branch}"

        try:
            with mock.patch.dict("os.environ", {"GIT_EDITOR": "true"}):
                try:
                    repo.git.cherry_pick(*args)
                except git.GitCommandError as e:
                    if "is not a merge." in e.stderr:
                        print("Likely not a merge PR...Attempting squash and merge picking.")
                        args = (merge_sha,)
                        repo.git.cherry_pick(*args)
                    else:
                        raise

        except git.GitCommandError as e:
            if ("git commit --allow-empty" in e.stderr.lower()) or (
                "git commit --allow-empty" in e.stdout.lower()
            ):
                session.post_comment(
                    comment_url,
                    "Can't Dooooo.... It seem like this is already backported (commit is empty)."
                    "I won't do anything. MrMeeseeks out.",
                )
                print(e.stderr)
                print("----")
                print(e.stdout)
                print("----")
                s_reason = "empty commit"
                keen_stats()
                return
            elif "after resolving the conflicts" in e.stderr.lower():
                # TODO, here we should also do a git merge --abort
                # to avoid thrashing the cache at next backport request.
                cmd = " ".join(pipes.quote(arg) for arg in sys.argv)
                print(
                    "\nPatch did not apply. Resolve conflicts (add, not commit), then re-run `%s`"
                    % cmd,
                    file=sys.stderr,
                )
                session.post_comment(
                    comment_url,
                    f"""Owee, I'm MrMeeseeks, Look at me.

There seem to be a conflict, please backport manually. Here are approximate instructions:

1. Checkout backport branch and update it.

```
git checkout {target_branch}
git pull
```

2. Cherry pick the first parent branch of the this PR on top of the older branch:
```
git cherry-pick -x -m1 {merge_sha}
```

3. You will likely have some merge/cherry-pick conflict here, fix them and commit:

```
git commit -am {msg!r}
```

4. Push to a named branch:

```
git push YOURFORK {target_branch}:{remote_submit_branch}
```

5. Create a PR against branch {target_branch}, I would have named this PR:

> "Backport PR #{prnumber} on branch {target_branch} ({prtitle})"

And apply the correct labels and milestones.

Congratulations — you did some good work! Hopefully your backport PR will be tested by the continuous integration and merged soon!

Remember to remove the `Still Needs Manual Backport` label once the PR gets merged.

If these instructions are inaccurate, feel free to [suggest an improvement](https://github.com/MeeseeksBox/MeeseeksDev).
                """,
                )
                org = payload["repository"]["owner"]["login"]
                repo = payload["repository"]["name"]
                num = payload.get("issue", payload).get("number")
                url = f"https://api.github.com/repos/{org}/{repo}/issues/{num}/labels"
                print("trying to apply still needs manual backport")
                reply = session.ghrequest("POST", url, json=["Still Needs Manual Backport"])
                print("Should be applied:", reply)
                s_reason = "conflicts"
                keen_stats()
                return
            else:
                session.post_comment(
                    comment_url,
                    "Oops, something went wrong applying the patch ... Please have a look at my logs.",
                )
                print(e.stderr)
                print("----")
                print(e.stdout)
                print("----")
                s_reason = "Unknown error line 491"
                keen_stats()
                return
        except Exception as e:
            session.post_comment(
                comment_url, "Hum, I actually crashed, that should not have happened."
            )
            if hasattr(e, "stderr"):
                print(
                    "\n" + e.stderr.decode("utf8", "replace"),
                    file=sys.stderr,
                )
            print("\n" + repo.git.status(), file=sys.stderr)
            add_event("error", {"git_crash": 1})
            s_reason = "Unknown error line 501"
            keen_stats()

            return

        # write the commit message
        repo.git.commit("--amend", "-m", msg)

        print("== PR #%i applied, with msg:" % prnumber)
        print()
        print(msg)
        print("== ")

        # Push the backported work
        print("== Pushing work....:")
        succeeded = True
        try:
            print(f"Trying to push to {remote_submit_branch} of {session.personal_account_name}")
            repo.remotes[session.personal_account_name].push(
                f"workbranch:{remote_submit_branch}"
            ).raise_if_error()
        except Exception as e:
            import traceback

            content = traceback.format_exc()
            print(content.replace(session.personal_account_token, "..."))

            print("could not push to self remote")
            s_reason = "Could not push"
            keen_stats()

            session.post_comment(
                comment_url,
                f"Could not push to {remote_submit_branch} due to error, aborting.",
            )
            print(e)
            succeeded = False

        repo.git.checkout(default_branch)
        repo.branches.workbranch.delete(repo, "workbranch", force=True)

        # TODO checkout the default_branch and get rid of branch

        if not succeeded:
            return

        # Make the PR on GitHub
        print(
            "try to create PR with milestone",
            milestone_number,
            "and labels",
            labels_names,
        )
        new_pr = session.personal_request(
            "POST",
            f"https://api.github.com/repos/{org_name}/{repo_name}/pulls",
            json={
                "title": f"Backport PR #{prnumber} on branch {target_branch} ({prtitle})",
                "body": msg,
                "head": f"{session.personal_account_name}:{remote_submit_branch}",
                "base": target_branch,
            },
        ).json()

        new_number = new_pr["number"]
        resp = session.ghrequest(
            "PATCH",
            f"https://api.github.com/repos/{org_name}/{repo_name}/issues/{new_number}",
            json={"milestone": milestone_number, "labels": labels_names},
        )
        # print(resp.json())
    except Exception as e:
        extra_info = ""
        if maybe_wrong_named_branch:
            extra_info = (
                "\n\n It seems that the branch you are trying to backport to does not exist."
            )
        session.post_comment(
            comment_url,
            "Something went wrong ... Please have a look at my logs." + extra_info,
        )
        add_event("error", {"unknown_crash": 1})
        print("Something went wrong")
        print(e)
        s_reason = "Remote branch does not exist"
        keen_stats()
        raise

    resp.raise_for_status()

    print("Backported as PR", new_number)
    s_reason = "Success"
    s_success = True
    keen_stats()
    return new_pr


@admin
def tag(session, payload, arguments, local_config=None):
    "tag[, tag, [...] ]"
    print("Got local config for tag: ", local_config)
    org = payload["repository"]["owner"]["login"]
    repo = payload["repository"]["name"]
    num = payload.get("issue", payload.get("pull_request")).get("number")
    url = f"https://api.github.com/repos/{org}/{repo}/issues/{num}/labels"
    arguments = arguments.replace("'", '"')
    quoted = re.findall(r"\"(.+?)\"", arguments.replace("'", '"'))
    for q in quoted:
        arguments = arguments.replace('"%s"' % q, "")
    tags = [arg.strip() for arg in arguments.split(",") if arg.strip()] + quoted
    print("raw tags:", tags)
    to_apply = []
    not_applied = []
    try:
        label_payload = session.ghrequest(
            "GET", f"https://api.github.com/repos/{org}/{repo}/labels"
        )

        label_payloads = [label_payload]

        def get_next_link(req):
            all_links = req.headers.get("Link")
            if 'rel="next"' in all_links:
                links = all_links.split(",")
                next_link = [l for l in links if "next" in l][0]  # assume only one.
                if next_link:
                    return next_link.split(";")[0].strip(" <>")

        # let's assume no more than 200 labels
        resp = label_payload
        try:
            for i in range(10):
                print("get labels page", i)
                next_link = get_next_link(resp)
                if next_link:
                    resp = session.ghrequest("GET", next_link)
                    label_payloads.append(resp)
                else:
                    break
        except Exception:
            traceback.print_exc()

        know_labels = []
        for p in label_payloads:
            know_labels.extend([label["name"] for label in p.json()])
        print("known labels", know_labels)

        not_known_tags = [t for t in tags if t not in know_labels]
        known_tags = [t for t in tags if t in know_labels]
        print("known tags", known_tags)
        print("known labels", not_known_tags)

        # try to look at casing
        nk = []
        known_lower_normal = {l.lower(): l for l in know_labels}
        print("known labels lower", known_lower_normal)
        for t in not_known_tags:
            target = known_lower_normal.get(t.lower())
            print("mapping t", t, target)
            if target:
                known_tags.append(t)
            else:
                print("will not apply", t)
                nk.append(t)

        to_apply = known_tags
        not_applied = nk
    except Exception:
        print(red + "something went wrong getting labels" + normal)

        traceback.print_exc()
    if local_config:
        only = set(local_config.get("only", []))
        any_tags = local_config.get("any", False)
        if any_tags:
            print("not filtering, any tags set")
        elif only:
            allowed_tags = [t for t in to_apply if t.lower() in only]
            not_allowed_tags = [t for t in to_apply if t.lower() not in only]

            print("will only allow", allowed_tags)
            print("will refuse", not_allowed_tags)
            to_apply = allowed_tags
            not_applied.extend(not_allowed_tags)
    if to_apply:
        session.ghrequest("POST", url, json=to_apply)
    if not_applied:
        comment_url = payload.get("issue", payload.get("pull_request"))["comments_url"]
        lf = "`,`".join(not_applied)
        user = payload.get("comment", {}).get("user", {}).get("login", None)
        session.post_comment(
            comment_url,
            f"Aww {user}, I was not able to apply the following label(s): `{lf}`. Either "
            "because they are not existing labels on this repository or because you do not have the permission to apply these."
            "I tried my best to guess by looking at the casing, but I was unable to find matching labels.",
        )


@admin
def untag(session, payload, arguments, local_config=None):
    "tag[, tag, [...] ]"
    org = payload["repository"]["owner"]["login"]
    repo = payload["repository"]["name"]
    num = payload.get("issue", payload.get("pull_request")).get("number")
    tags = [arg.strip() for arg in arguments.split(",")]
    name = "{name}"
    url = f"https://api.github.com/repos/{org}/{repo}/issues/{num}/labels/{name}"
    no_untag = []
    for tag in tags:
        try:
            session.ghrequest("DELETE", url.format(name=tag))
        except Exception:
            no_untag.append(tag)
    print("was not able to remove tags:", no_untag)


@write
def migrate_issue_request(
    *,
    session: Session,
    payload: dict,
    arguments: str,
    local_config: Optional[dict] = None,
) -> Generator:
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
        session.post_comment(payload["issue"]["comments_url"], "It appears that I can't do that")
        return

    issue_title = payload["issue"]["title"]
    issue_body = payload["issue"]["body"]
    original_org = payload["repository"]["owner"]["login"]
    original_repo = payload["repository"]["name"]
    original_poster = payload["issue"]["user"]["login"]
    original_number = payload["issue"]["number"]
    migration_requester = payload["comment"]["user"]["login"]
    request_id = payload["comment"]["id"]
    original_labels = [l["name"] for l in payload["issue"]["labels"]]

    if original_labels:
        available_labels = target_session.ghrequest(
            "GET",
            f"https://api.github.com/repos/{org}/{repo}/labels",
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

    original_comments = session.ghrequest("GET", payload["issue"]["comments_url"], None).json()

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
        body = "I was not able to apply the following label(s): %s " % ",".join(not_set_labels)
        target_session.post_comment(new_comment_url, body=body)

    session.post_comment(
        payload["issue"]["comments_url"],
        body="Done as {}/{}#{}.".format(org, repo, new_issue["number"]),
    )
    session.ghrequest("PATCH", payload["issue"]["url"], json={"state": "closed"})


@write
def quote(*, session, payload, arguments, local_config=None):
    if arguments.lower() == "over the world":
        comment_url = payload["issue"]["comments_url"]
        user = payload["issue"]["user"]["login"]
    session.post_comment(
        comment_url,
        """
> MeeseeksDev: Gee, {user}, what do you want to do tonight?
{user}: The same thing we do every night, MeeseeksDev - try to take over the world!
""".format(
            user=user
        ),
    )
