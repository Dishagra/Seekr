"""GitHub connector — official REST API only.

Identifier: GitHub username (login).
Set GITHUB_TOKEN for higher rate limits (60/h unauthenticated, 5000/h with token).
Extracts: profile fields, language skills evidenced by repos, top repos as projects,
company as an affiliation, blog/twitter as cross-profile resolution links.
"""

import os
from collections import Counter

from ..normalize import EvidenceItem, NormalizedProfile, OrgAffiliation, ProjectData
from .base import BaseConnector

API = "https://api.github.com"
MAX_REPOS_AS_PROJECTS = 10


class GitHubConnector(BaseConnector):
    source = "github"
    source_type = "code_hosting"

    def default_headers(self) -> dict:
        headers = super().default_headers()
        headers["Accept"] = "application/vnd.github+json"
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def fetch(self, identifier: str) -> NormalizedProfile:
        user = self.get_json(f"{API}/users/{identifier}")
        repos = self.get_json(
            f"{API}/users/{identifier}/repos",
            params={"per_page": 100, "sort": "pushed", "type": "owner"},
        )
        return self.normalize(user, repos)

    def renormalize(self, external_id: str, raw: dict) -> NormalizedProfile:
        return self.normalize(raw["user"], raw["repos"])

    def search_users(
        self, location: str | None = None, query: str = "", *,
        min_followers: int | None = None, min_repos: int | None = None,
        page: int = 1, per_page: int = 100,
    ) -> tuple[list[str], int]:
        """Search users by location/qualifiers. Returns (logins, total_count).

        GitHub caps any search at 1,000 results, so a large harvest must be
        sliced (by city, follower band, language) rather than paged past that.
        """
        parts = [query] if query else []
        if location:
            parts.append(f'location:"{location}"')
        if min_followers:
            parts.append(f"followers:>={min_followers}")
        if min_repos:
            parts.append(f"repos:>={min_repos}")
        parts.append("type:user")
        data = self.get_json(
            f"{API}/search/users",
            params={"q": " ".join(parts), "per_page": per_page, "page": page},
        )
        return [u["login"] for u in data.get("items", [])], data.get("total_count", 0)

    def normalize(self, user: dict, repos: list[dict]) -> NormalizedProfile:
        login = user["login"]
        own_repos = [r for r in repos if not r.get("fork")]

        evidence: list[EvidenceItem] = []
        lang_counts = Counter(r["language"] for r in own_repos if r.get("language"))
        for lang, count in lang_counts.most_common():
            evidence.append(
                EvidenceItem(
                    attribute_type="skill",
                    value=lang,
                    extracted_info=f"{count} public repositories primarily in {lang}",
                    url=user.get("html_url"),
                    confidence=min(0.9, 0.4 + 0.05 * count),
                )
            )
        if user.get("bio"):
            evidence.append(
                EvidenceItem(
                    attribute_type="bio",
                    value=user["bio"][:512],
                    url=user.get("html_url"),
                    confidence=0.6,
                )
            )

        organizations: list[OrgAffiliation] = []
        company = (user.get("company") or "").strip()
        if company:
            organizations.append(
                OrgAffiliation(
                    name=company.lstrip("@"), relation="worked_at",
                    org_type="company", is_current=True,
                )
            )

        websites: list[str] = []
        linked: list[str] = []
        if user.get("blog"):
            websites.append(user["blog"])
        if user.get("twitter_username"):
            linked.append(f"https://twitter.com/{user['twitter_username']}")

        top_repos = sorted(own_repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)
        projects = [
            ProjectData(
                name=r["name"],
                description=r.get("description"),
                url=r.get("html_url"),
                technologies=[r["language"]] if r.get("language") else [],
                activity={
                    "stars": r.get("stargazers_count", 0),
                    "forks": r.get("forks_count", 0),
                    "open_issues": r.get("open_issues_count", 0),
                },
                started_at=(r.get("created_at") or "")[:10] or None,
                last_active_at=(r.get("pushed_at") or "")[:10] or None,
                role="owner",
            )
            for r in top_repos[:MAX_REPOS_AS_PROJECTS]
        ]

        emails = [user["email"]] if user.get("email") else []

        return NormalizedProfile(
            source=self.source,
            source_type=self.source_type,
            external_id=login,
            url=user.get("html_url") or f"https://github.com/{login}",
            raw={"user": user, "repos": repos},
            name=user.get("name"),
            aliases=[login],
            location=user.get("location"),
            summary=user.get("bio"),
            emails=emails,
            usernames=[f"github:{login.lower()}"],
            websites=websites,
            linked_urls=linked,
            organizations=organizations,
            evidence=evidence,
            projects=projects,
        )
