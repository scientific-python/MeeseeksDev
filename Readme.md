# MeeseeksBox

A base for stateless GitHub Bot. 

## setup.

These are the environment variable that need to be set.

 - `INTEGRATION_ID` The integration ID given to you by GitHub when you create
   an integration
 - `BOTNAME` Name of the integration on GitHub, should be without the leading
   `@`, and with the `[bot]`. This is used for the bot to react to his own name, and not reply to itself...
