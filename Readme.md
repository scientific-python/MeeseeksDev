# MeeseeksBox

A base for stateless GitHub Bot. 

See what is a [MeeseeksDev and a MeeseeksBox](https://www.youtube.com/watch?v=qUYvIAP3qQk)

## Hosted for you

We host MeeseeksBoxes and will expose them as GitHub Integrations so you don't
have to host and run your own, but you can if you want, it should be pretty
simple. 

The advantage of having One and only one box, is to do cross repository
operations.

## What can a MeeseeksBox do ?

### @MeeseeksDev Hello

Respond with

> Hello {user} look at me, I'm Mr Meeseeks

To test whether a Meeseeks understand you.

### @MeeseeksDev backport [to] {branch}

If issued from a  PR which is merged, attempt to backport (cherry-pick the
merge commit) on an older branch and submit a PR with this backport (on said branch)

No option to push directly. 

Repo admins only

### @MeeseeksDev pep8ify

(in progress)

If issued from a PR, will apply autopep8 to the current lines changed by this
PR, and push an extra commit to it that fixes pep8. 

Code in progress and due to GitHub API limitation only works if MeeseeksDev
also available on Source repo of the PR. 

Repo admins only, plan to make it available to PR author as well. 

MeeseeksDev Bot need to be installed on the PR source repository for this to work.
If it's not it will ask you to do so. 

### @MeeseeksDev migrate [to] {target org/repo}

Needs MeeseeksBox to be installed on both current and target repo. Command
issuer to be admin on both. 

MeeseeksDev will open a similar issue, replicate all comments with links to
first, migrate labels (if possible). 


### @MeeseeksDev close

Close the issue. Useful when replying by mail

### @MeeseeksDev open

Reopen the issue.

### @MeeseeksDev tag bug, question, Need Contributor

Tag with said tags if availlable (comma separated, need to be exact match)

### @MeeseeksDev untag bug, question, Need Contributor

Remove said tags if present (comma separated, need to be exact match)


## Simple extension.

Most extension and new command for the MeeseeksBox are only one function, for
example here is how to let everyone request the zen of Python:

```python
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
        Sparse is better than dense.
        ....
        Although never is often better than *right* now.
        Namespaces are one honking great idea -- let's do more of those!
        ```
        """
    ))
```

The `session` object is authenticated with the repository the command came from.
If you need to authenticate with another repository with MeeseeksBox installed `yield` the `org/repo` slug.

```python
@admin
def foo(*, session, payload, argument):
    other_session = yield 'MeeseeksBox/MeeseeksBox'
    if other_session:
        print('you are allowed to access MeeseeksBox/MeeseeksBox')
        other_session.do_stuff()
    else:
        session.post_comment("Sorry Jerry you are not allowed to do that.")
```


# Why do you request so much permission ?

GitHub API does not allow to change permissions once given. We don't want you
to go though the process of reinstalling all integrations.

We would like to request less permission if necessary. 



# Setup.

These are the environment variable that need to be set.

 - `INTEGRATION_ID` The integration ID given to you by GitHub when you create
   an integration
 - `BOTNAME` Name of the integration on GitHub, should be without the leading
   `@`, and with the `[bot]`. This is used for the bot to react to his own name, and not reply to itself...

   TODO

# Warnings

This is still alpha software, user and org that can use it are still hardcoded.
If you want access open an issue for me to whitelist your org and users.

Because of GitHub API limitation, MeeseeksBox can not yet make the distinction
between read-only and read-write collaborators.


