from ..meeseeksbox.core import process_mentionning_comment
import textwrap
import re



def test1():
    botname = 'meeseeksdev'
    reg = re.compile("@?" + re.escape(botname) + "(?:\[bot\])?", re.IGNORECASE)

    assert process_mentionning_comment(textwrap.dedent('''
        @meeseeksdev nothing
        @meeseeksdev[bot] do nothing
        meeseeksdev[bot] do something

                                
    '''), reg) == [['nothing', None],
                   ['do', 'nothing'], 
                   ['do', 'something']]



    
