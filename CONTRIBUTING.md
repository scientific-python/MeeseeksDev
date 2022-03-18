# Contributing

## Test Deployment

- Install the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli#download-and-install).

You will need to have an account in both Heroku.

Log in to Heroku:

```bash
heroku login
```

If creating, run:

```bash
heroku create meeseeksdev
```

Otherwise, run:

```bash
heroku git:remote -a meeseeksdev
```

Then run:

```
git push heroku $(git rev-parse --abbrev-ref HEAD):master
heroku open
```

Browse to `/hooks/github` and verify page render.

### Heroku Configuration

You will need a Github token with access to cancel builds. This 

This needs to be setup on the [Heroku Application settings](https://dashboard.heroku.com/apps/jupyterlab-bot/settings)

On the `Config Vars`. section set a key `GITHUB_ACCESS_TOKEN` with the value of the generated token.

GITHUB_INTEGRATION_ID
B64KEY
GITHUB_BOT_NAME
WEBHOOK_SECRET
PERSONAL_ACCOUNT_NAME
PERSONAL_ACCOUNT_TOKEN
