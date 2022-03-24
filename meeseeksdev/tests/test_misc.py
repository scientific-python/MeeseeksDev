import re
import textwrap

from ..meeseeksbox.core import process_mentionning_comment


def test1():
    botname = "meeseeksdev"
    reg = re.compile("@?" + re.escape(botname) + r"(?:\[bot\])?", re.IGNORECASE)

    assert (
        process_mentionning_comment(
            textwrap.dedent(
                """
        @meeseeksdev nothing
        @meeseeksdev[bot] do nothing
        meeseeksdev[bot] do something
        @meeseeksdev please nothing
        @meeseeksdev run something


    """
            ),
            reg,
        )
        == [
            ["nothing", None],
            ["do", "nothing"],
            ["do", "something"],
            ["nothing", None],
            ["something", None],
        ]
    )
