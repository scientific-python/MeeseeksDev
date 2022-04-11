"""
Utility functions to work with github.
"""
import datetime
import json
import pipes
import re
import shlex
import subprocess
from typing import Any, Dict, Optional, cast

import jwt
import requests

from .scopes import Permission

green = "\033[0;32m"
yellow = "\033[0;33m"
red = "\033[0;31m"
normal = "\033[0m"


API_COLLABORATORS_TEMPLATE = (
    "https://api.github.com/repos/{org}/{repo}/collaborators/{username}/permission"
)
ACCEPT_HEADER_V3 = "application/vnd.github.v3+json"
ACCEPT_HEADER = "application/vnd.github.machine-man-preview"
ACCEPT_HEADER_KORA = "json,application/vnd.github.korra-preview"
ACCEPT_HEADER_SYMMETRA = "application/vnd.github.symmetra-preview+json"

"""
Regular expression to relink issues/pr comments correctly.

Pay attention to not relink things like foo#23 as they already point to a
specific repository.
"""
RELINK_RE = re.compile(r"(?:(?<=[:,\s])|(?<=^))(#\d+)\\b")


def add_event(*args):
    """Attempt to add an event to keen, print the event otherwise"""
    try:
        import keen

        keen.add_event(*args)
    except Exception:
        print("Failed to log keen event:")
        print(f"   {args}")


def run(cmd, **kwargs):
    """Print a command and then run it."""
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    print(" ".join(map(pipes.quote, cmd)))
    return subprocess.run(cmd, **kwargs)


def fix_issue_body(
    body,
    original_poster,
    original_repo,
    original_org,
    original_number,
    migration_requester,
):
    """
    This, for now does only simple fixes, like link to the original issue.
    This should be improved to quote mention of people
    """

    body = RELINK_RE.sub(f"{original_org}/{original_repo}\\1", body)

    return f"""{body}\n\n----
    \nOriginally opened as {original_org}/{original_repo}#{original_number} by @{original_poster}, migration requested by @{migration_requester}
    """


def fix_comment_body(body, original_poster, original_url, original_org, original_repo):
    """
    This, for now does only simple fixes, like link to the original comment.

    This should be improved to quote mention of people
    """

    body = RELINK_RE.sub("{org}/{repo}\\1".format(org=original_org, repo=original_repo), body)

    return """[`@{op}` commented]({original_url}): {body}""".format(
        op=original_poster, original_url=original_url, body=body
    )


class Authenticator:
    def __init__(
        self,
        integration_id: int,
        rsadata: Optional[str],
        personal_account_token: Optional[str],
        personal_account_name: Optional[str],
    ):
        self.since = int(datetime.datetime.now().timestamp())
        self.duration = 60 * 10
        self._token = None
        self.integration_id = integration_id
        self.rsadata = rsadata
        self.personal_account_token = personal_account_token
        self.personal_account_name = personal_account_name
        self.idmap: Dict[str, str] = {}
        self._org_idmap: Dict[str, str] = {}
        self._session_class = Session

    def session(self, installation_id: str) -> "Session":
        """
        Given and installation id, return a session with the right credentials
        """
        # print('spawning session for repo', [(k,v) for k,v in self.idmap.items() if v == installation_id])
        # print('DEBUG: ', self.idmap, installation_id)
        return self._session_class(
            self.integration_id,
            self.rsadata,
            installation_id,
            self.personal_account_token,
            self.personal_account_name,
        )

    def get_session(self, org_repo):
        """Given an org and repo, return a session with the right credentials."""
        # First try - see if we already have the auth.
        if org_repo in self.idmap:
            return self.session(self.idmap[org_repo])

        # Next try - see if this is a newly authorized repo in an
        # org that we've seen.
        org, _ = org_repo.split("/")
        if org in self._org_idmap:
            self._update_installation(self._org_idmap[org])
            if org_repo in self.idmap:
                return self.session(self.idmap[org_repo])

        # TODO: if we decide to allow any org without an allowlist,
        # we should make the org list dynamic.  We would re-scan
        # the list of installations here and update our mappings.

    def list_installations(self) -> Any:
        """List the installations for the app."""
        installations = []

        url = "https://api.github.com/app/installations"
        while True:
            response = self._integration_authenticated_request("GET", url)
            installations.extend(response.json())
            if "next" in response.links:
                url = response.links["next"]["url"]
                continue
            break

        return installations

    def _build_auth_id_mapping(self):
        """
        Build an organisation/repo -> installation_id mappingg in order to be able
        to do cross repository operations.
        """
        if not self.rsadata:
            print("Skipping auth_id_mapping build since there is no B64KEY set")
            return

        self._installations = self.list_installations()
        for installation in self._installations:
            self._update_installation(installation)

    def _update_installation(self, installation):
        iid = installation["id"]
        session = self.session(iid)
        try:
            # Make sure we get all pages.
            url = installation["repositories_url"]
            while True:
                res = session.ghrequest("GET", url)
                repositories = res.json()
                for repo in repositories["repositories"]:
                    self.idmap[repo["full_name"]] = iid
                    self._org_idmap[repo["owner"]["login"]] = iid
                if "next" in res.links:
                    url = res.links["next"]["url"]
                    continue
                break

        except Forbidden:
            print("Forbidden for", iid)
            return

    def _integration_authenticated_request(self, method, url, json=None):
        self.since = int(datetime.datetime.now().timestamp())
        payload = dict(
            {
                "iat": self.since,
                "exp": self.since + self.duration,
                "iss": self.integration_id,
            }
        )

        assert self.rsadata is not None
        tok = jwt.encode(payload, key=self.rsadata, algorithm="RS256")

        headers = {
            "Authorization": f"Bearer {tok}",
            "Accept": ACCEPT_HEADER_V3,
            "Host": "api.github.com",
            "User-Agent": "python/requests",
        }
        req = requests.Request(method, url, headers=headers, json=json)
        prepared = req.prepare()
        with requests.Session() as s:
            return s.send(prepared)


class Forbidden(Exception):
    pass


class Session(Authenticator):
    def __init__(
        self,
        integration_id,
        rsadata,
        installation_id,
        personal_account_token,
        personal_account_name,
    ):
        super().__init__(integration_id, rsadata, personal_account_token, personal_account_name)
        self.installation_id = installation_id

    def token(self) -> str:
        now = datetime.datetime.now().timestamp()
        if (now > self.since + self.duration - 60) or (self._token is None):
            self.regen_token()
        assert self._token is not None
        return self._token

    def regen_token(self) -> None:
        method = "POST"
        url = f"https://api.github.com/app/installations/{self.installation_id}/access_tokens"
        resp = self._integration_authenticated_request(method, url)
        if resp.status_code == 403:
            raise Forbidden(self.installation_id)

        try:
            self._token = json.loads(resp.content.decode())["token"]
        except Exception:
            raise ValueError(resp.content, url)

    def personal_request(
        self, method: str, url: str, json: Optional[dict] = None, raise_for_status: bool = True
    ) -> requests.Response:
        """
        Does a request but using the personal account name and token
        """
        if not json:
            json = {}

        def prepare():
            headers = {
                "Authorization": "token {}".format(self.personal_account_token),
                "Host": "api.github.com",
                "User-Agent": "python/requests",
            }
            req = requests.Request(method, url, headers=headers, json=json)
            return req.prepare()

        with requests.Session() as s:
            response = s.send(prepare())
            if response.status_code == 401:
                self.regen_token()
                response = s.send(prepare())
            if raise_for_status:
                response.raise_for_status()
            return response

    def ghrequest(
        self,
        method: str,
        url: str,
        json: Optional[dict] = None,
        *,
        override_accept_header: Optional[str] = None,
        raise_for_status: Optional[bool] = True,
    ) -> requests.Response:
        accept = ACCEPT_HEADER
        if override_accept_header:
            accept = override_accept_header

        def prepare():
            atk = self.token()
            headers = {
                "Authorization": "Bearer {}".format(atk),
                "Accept": accept,
                "Host": "api.github.com",
                "User-Agent": "python/requests",
            }
            print(f"Making a {method} call to {url}")
            req = requests.Request(method, url, headers=headers, json=json)
            return req.prepare()

        with requests.Session() as s:
            response = s.send(prepare())
            if response.status_code == 401:
                self.regen_token()
                response = s.send(prepare())
            if raise_for_status:
                response.raise_for_status()
            rate_limit = response.headers.get("X-RateLimit-Limit", -1)
            rate_remaining = response.headers.get("X-RateLimit-Limit", -1)
            if rate_limit:
                repo_name_list = [k for k, v in self.idmap.items() if v == self.installation_id]
                repo_name = "no-repo"
                if len(repo_name_list) == 1:
                    repo_name = repo_name_list[0]
                elif len(repo_name_list) == 0:
                    repo_name = "no-matches"
                else:
                    repo_name = "multiple-matches"

                add_event(
                    "gh-rate",
                    {
                        "limit": int(rate_limit),
                        "rate_remaining": int(rate_remaining),
                        "installation": repo_name,
                    },
                )
            return response

    def _get_permission(self, org: str, repo: str, username: str) -> Permission:
        get_collaborators_query = API_COLLABORATORS_TEMPLATE.format(
            org=org, repo=repo, username=username
        )
        resp = self.ghrequest(
            "GET",
            get_collaborators_query,
            None,
            override_accept_header=ACCEPT_HEADER_KORA,
        )
        resp.raise_for_status()
        permission = resp.json()["permission"]
        print("found permission", permission, "for user ", username, "on ", org, repo)
        return cast(Permission, getattr(Permission, permission))

    def has_permission(
        self, org: str, repo: str, username: str, level: Optional[Permission] = None
    ) -> bool:
        """ """
        if not level:
            level = Permission.none

        return self._get_permission(org, repo, username).value >= level.value

    def post_comment(self, comment_url: str, body: str) -> None:
        self.ghrequest("POST", comment_url, json={"body": body})

    def get_collaborator_list(self, org: str, repo: str) -> Optional[Any]:
        get_collaborators_query = "https://api.github.com/repos/{org}/{repo}/collaborators".format(
            org=org, repo=repo
        )
        resp = self.ghrequest("GET", get_collaborators_query, None)
        if resp.status_code == 200:
            return resp.json()
        else:
            resp.raise_for_status()
            return None

    def create_issue(
        self,
        org: str,
        repo: str,
        title: str,
        body: str,
        *,
        labels: Optional[list] = None,
        assignees: Optional[list] = None,
    ) -> requests.Response:
        arguments: dict = {"title": title, "body": body}

        if labels:
            if type(labels) in (list, tuple):
                arguments["labels"] = labels
            else:
                raise ValueError("Labels must be a list of a tuple")

        if assignees:
            if type(assignees) in (list, tuple):
                arguments["assignees"] = assignees
            else:
                raise ValueError("Assignees must be a list or a tuple")

        return self.ghrequest(
            "POST",
            "https://api.github.com/repos/{}/{}/issues".format(org, repo),
            json=arguments,
        )


def clear_caches():
    """Clear local caches"""
    print("\n\n====Clearing all caches===")
    run("pip cache purge")
    run("pre-commit clean")
    print("====Finished clearing caches===\n\n")
