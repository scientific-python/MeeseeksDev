"""
Define a few commands
"""

import random

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
        ```python
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
