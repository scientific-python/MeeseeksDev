"""
Test basic functionality of the MeeseeksBox system
"""

from meeseeksbox import process_mentionning_comment

def test_command_finding():
    """
    Test that mentionning the bot in various context (and several time in a
    comment) does parse correctly.
    """
    
    botname = 'BotName'
    
    parsed = process_mentionning_comment("""
    botname hello
        Hey @botname do stuff
    @botname backport to 4.x
@botname[bot] zen
    @BotName[bot] migrate to ipython/notebook
    """, botname)
    
    assert len(parsed) == 5, 'Bot was not able to correctly detec on of the mention %s' % parsed
    
    
