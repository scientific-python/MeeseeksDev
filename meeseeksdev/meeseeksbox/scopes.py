"""
Define various scopes
"""


def admin(function):
    function.scope='admin'
    return function

def everyone(function):
    function.scope='everyone'
    return function
