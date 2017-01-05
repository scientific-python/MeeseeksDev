"""
Define various scopes
"""

from enum import Enum


class Permission(Enum):
    none = 0
    read = 1
    write = 2
    admin = 4


def admin(function):
    function.scope = Permission.admin
    return function


def read(function):
    function.scope = Permission.read
    return function


def write(function):
    function.scope = Permission.write
    return function


def everyone(function):
    function.scope = Permission.none
    return function
