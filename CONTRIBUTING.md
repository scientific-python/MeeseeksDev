# Contributing

## Test Deployment

- Install the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli#download-and-install).

You will need to have an account in Heroku.

Log in to Heroku:

```bash
heroku login
```

If creating, run:

```bash
heroku create meeseeksdev-$USER
```

Otherwise, run:

```bash
heroku git:remote -a meeseeksdev-$USER
```

Then run:

```
git push heroku $(git rev-parse --abbrev-ref HEAD):master
heroku open
```

### GitHub App Configuration

Create a GitHub App for testing on your account
Homepage URL: https://meeseeksdev-$USER.herokuapp.com/
Webhook URL: https://meeseeksdev-$USER.herokuapp.com/webhook
Webhook Secret: Set and store as WEBHOOK_SECRET env variable
Private Key: Generate and store as B64KEY env variable

Grant write access to content, issues, and users.
Subscribe to Issue and Issue Comment Events.

Install the application on your user account, at least in your MeeseeksDev fork.

### Heroku Configuration

You will need a Github token with access to cancel builds. This

This needs to be setup on the [Heroku Application settings](https://dashboard.heroku.com/apps/jupyterlab-bot/settings)

On the `Config Vars`. section set the following keys::

```
GITHUB_INTEGRATION_ID="<App ID of the Application>"
B64KEY="<B64 encoding of entire pem file>"
GITHUB_BOT_NAME="<meeseeksdev-$USER>"
WEBHOOK_SECRET="<value from the webhooks add above>"
PERSONAL_ACCOUNT_NAME="<account name>"
PERSONAL_ACCOUNT_TOKEN="<github personal access token with repo access>"
```
