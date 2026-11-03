"""Refresh the public profile card using GitHub CLI and Python's standard library."""

import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
LOGIN = "w940853815"
WAKATIME = "https://wakatime.com/badge/user/8f145c8d-599d-496b-82c7-91f941d33614.svg"
PAGE = "pageInfo { hasNextPage endCursor } nodes"
REPO = "nameWithOwner isPrivate owner { login }"


def api(endpoint, payload=None):
    command = ["gh", "api", endpoint]
    if payload is not None:
        command += ["--input", "-"]
    for attempt in range(3):
        try:
            result = subprocess.run(command, input=json.dumps(payload) if payload else None,
                                    text=True, capture_output=True, timeout=120, check=True)
            data = json.loads(result.stdout)
            if isinstance(data, dict) and data.get("errors"):
                raise RuntimeError(str(data["errors"]))
            return data
        except (subprocess.SubprocessError, RuntimeError) as error:
            if attempt == 2:
                detail = error.stderr if isinstance(error, subprocess.CalledProcessError) else str(error)
                raise RuntimeError(f"GitHub request failed: {detail}") from error
            time.sleep(2 ** attempt)


def graphql(query, **variables):
    return api("graphql", {"query": query, "variables": variables})["data"]


def connection(query, field):
    after = None
    while True:
        page = graphql(query, login=LOGIN, after=after)["user"][field]
        yield from page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return
        after = page["pageInfo"]["endCursor"]
        if not after:
            raise ValueError("Missing pagination cursor")


def commit_totals(commits):
    seen = set()
    additions = deletions = 0
    for commit in commits:
        if commit["oid"] in seen or commit["parents"]["totalCount"] > 1:
            continue
        seen.add(commit["oid"])
        additions += commit["additions"]
        deletions += commit["deletions"]
    return additions, deletions


def repository_commits(name, author):
    owner, repo = name.split("/")
    after, ref = None, "HEAD"
    query = """query($owner:String!,$repo:String!,$author:ID!,$ref:String!,$after:String) {
      repository(owner:$owner,name:$repo) { isPrivate isEmpty
        object(expression:$ref) { ... on Commit { oid
          history(first:100,after:$after,author:{id:$author}) {
            pageInfo { hasNextPage endCursor }
            nodes { oid additions deletions parents { totalCount } }
          }
        } }
      }
    }"""
    while True:
        repository = graphql(query, owner=owner, repo=repo, author=author,
                             ref=ref, after=after)["repository"]
        if repository is None:
            raise ValueError(f"Repository unavailable: {name}")
        if repository["isPrivate"] or repository["isEmpty"]:
            return
        target = repository["object"]
        if target is None:
            raise ValueError(f"Default branch unavailable: {name}")
        ref = target["oid"]  # Keep pagination on one commit even if the branch advances.
        page = target["history"]
        yield from page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return
        after = page["pageInfo"]["endCursor"]


def parse_wakatime(svg):
    texts = {node.text.strip() for node in ET.fromstring(svg).iter()
             if node.tag.endswith("}text") and node.text}
    values = [text for text in texts if re.fullmatch(r"(?:[\d,]+\s+(?:days?|hrs?|mins?|secs?)\s*)+", text)]
    if len(values) != 1:
        raise ValueError("WakaTime badge does not contain a valid duration")
    return values[0]


def collect(now):
    user = graphql("""query($login:String!) { user(login:$login) {
      id createdAt followers { totalCount } following { totalCount }
    } }""", login=LOGIN)["user"]
    owned = list(connection("""query($login:String!,$after:String) { user(login:$login) {
      repositories(first:100,after:$after,ownerAffiliations:OWNER,privacy:PUBLIC) { """
                            + PAGE + " { " + REPO + " stargazerCount } } } }", "repositories"))
    repositories = {repo["nameWithOwner"] for repo in owned if not repo["isPrivate"]}
    owned_names = set(repositories)
    contributed = set()
    for year in range(int(user["createdAt"][:4]), now.year + 1):
        end = min(datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc), now)
        collection = graphql("""query($login:String!,$start:DateTime!,$end:DateTime!) {
          user(login:$login) { contributionsCollection(from:$start,to:$end) {
            totalRepositoriesWithContributedCommits
            commitContributionsByRepository(maxRepositories:100) {
              repository { nameWithOwner isPrivate }
            }
          } }
        }""", login=LOGIN, start=f"{year}-01-01T00:00:00Z", end=end.isoformat())["user"]["contributionsCollection"]
        if collection["totalRepositoriesWithContributedCommits"] > 100:
            raise ValueError(f"Contribution discovery exceeded 100 repositories in {year}")
        contributed.update(item["repository"]["nameWithOwner"]
                           for item in collection["commitContributionsByRepository"]
                           if not item["repository"]["isPrivate"])
    pulls = list(connection("""query($login:String!,$after:String) { user(login:$login) {
      pullRequests(first:100,after:$after,states:MERGED) { """ + PAGE
                            + " { repository { " + REPO + " } } } } }", "pullRequests"))
    public_pulls = [pull for pull in pulls if not pull["repository"]["isPrivate"]]
    contributed.update(pull["repository"]["nameWithOwner"] for pull in public_pulls)
    repositories.update(contributed)

    def commits():
        for index, name in enumerate(sorted(repositories), 1):
            print(f"Reading public history {index}/{len(repositories)}: {name}", flush=True)
            yield from repository_commits(name, user["id"])

    additions, deletions = commit_totals(commits())
    search = api("search/commits?" + urllib.parse.urlencode({"q": f"author:{LOGIN} is:public", "per_page": 1}))
    if search["incomplete_results"]:
        raise ValueError("GitHub commit search returned incomplete results")
    request = urllib.request.Request(WAKATIME, headers={"User-Agent": "github-profile-stats"})
    with urllib.request.urlopen(request, timeout=30) as response:
        wakatime = parse_wakatime(response.read())
    return {"updated_at": now.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M CST"),
            "repos": len(owned_names), "contributed": len(contributed - owned_names),
            "stars": sum(repo["stargazerCount"] for repo in owned if not repo["isPrivate"]),
            "commits": search["total_count"], "followers": user["followers"]["totalCount"],
            "following": user["following"]["totalCount"],
            "additions": additions, "deletions": deletions, "lines_of_code": additions - deletions,
            "merged_prs": len(public_pulls), "wakatime": wakatime}


def stats_svg(stats, mobile, dark):
    x, right = (24, 376) if mobile else (432, 1008)
    size = 13 if mobile else 16
    colors = {"label": "#ffa657" if dark else "#953800",
              "text": "#e6edf3" if dark else "#1f2328",
              "muted": "#9198a1" if dark else "#59636e",
              "green": "#7ee787" if dark else "#116329",
              "red": "#ff7b72" if dark else "#b42318"}
    result = ['<g id="profile-stats">']

    def text(value, px, y, role="text", anchor="start", font_size=size):
        result.append(f'<text x="{px}" y="{y}" fill="{colors[role]}" font-size="{font_size}" text-anchor="{anchor}">{escape(str(value))}</text>')

    def row(label, value, y):
        text(label + ":", x, y, "label")
        text(value, right, y, anchor="end")

    n = lambda key: f"{stats[key]:,}"
    if mobile:
        row("Repos", f'{n("repos")} {{Contributed: {n("contributed")}}}', 690)
        text("Stars:", x, 718, "label")
        text(n("stars"), 143, 718, anchor="end")
        text("Following:", 184, 718, "label")
        text(n("following"), right, 718, anchor="end")
        text("Commits:", x, 746, "label")
        text(n("commits"), 143, 746, anchor="end")
        text("Followers:", 184, 746, "label")
        text(n("followers"), right, 746, anchor="end")
        row("Lines of Code", n("lines_of_code"), 774)
        text(f'{n("additions")}++', x, 802, "green")
        text(f'{n("deletions")}--', right, 802, "red", "end")
        row("Merged PRs", n("merged_prs"), 830)
        row("WakaTime", stats["wakatime"], 858)
        text(stats["updated_at"], x, 899, "muted", font_size=11)
        text("Updated daily · public data", x, 917, "muted", font_size=11)
    else:
        text("Repos:", x, 446, "label")
        text(f'{n("repos")} {{Contributed: {n("contributed")}}}', x + 68, 446)
        text("Stars:", 844, 446, "label")
        text(n("stars"), right, 446, anchor="end")
        text("Commits:", x, 476, "label")
        text(n("commits"), x + 90, 476)
        text("Followers:", 660, 476, "label")
        text(n("followers"), 790, 476, anchor="end")
        text("Following:", 834, 476, "label")
        text(n("following"), right, 476, anchor="end")
        text("Lines of Code:", x, 506, "label")
        result.append(f'<text x="{x + 146}" y="506" fill="{colors["text"]}" font-size="16">{n("lines_of_code")} ( <tspan fill="{colors["green"]}">{n("additions")}++</tspan>, <tspan fill="{colors["red"]}">{n("deletions")}--</tspan> )</text>')
        row("Merged PRs", n("merged_prs"), 536)
        row("WakaTime", stats["wakatime"], 566)
        text(stats["updated_at"] + " · updated daily", right, 606, "muted", "end", 12)
    result.append("</g>")
    return "\n".join(result)


def render_card(source, stats, mobile, dark):
    height = 940 if mobile else 630
    width = 400 if mobile else 1040
    source = re.sub(r'height="\d+" viewBox="0 0 \d+ \d+"',
                    f'height="{height}" viewBox="0 0 {width} {height}"', source, count=1)
    source = re.sub(r'(<rect x=".5" y=".5" width="\d+" height=")\d+',
                    lambda match: match[1] + str(height - 1), source, count=1)
    source = re.sub(r'<desc id="desc">.*?</desc>',
                    '<desc id="desc">Panda avatar in ASCII art. wrd, FIT2ClOUD, Beijing. Public statistics updated daily. Select the card for the statistics methodology.</desc>', source, count=1)
    # The introduction stays authored SVG; only the marked statistics block is generated.
    start = source.find('<g id="profile-stats">')
    if start < 0:
        marker = '<text x="24" y="690"' if mobile else '<text x="432" y="446"'
        start = source.index(marker)
    return source[:start] + stats_svg(stats, mobile, dark) + "\n</g></svg>\n"


def publish(stats):
    outputs = {}
    for name in ("profile", "profile-dark", "profile-mobile", "profile-mobile-dark"):
        path = ROOT / "assets" / (name + ".svg")
        rendered = render_card(path.read_text(), stats, "mobile" in name, "dark" in name)
        ET.fromstring(rendered)
        outputs[path] = rendered
    readme = ROOT / "README.md"
    alt = ('wrd (w940853815) — FIT2ClOUD, Beijing; JumpServer contributor. '
           'Project stack: Python, Django, Go, Vue, JavaScript, TypeScript. '
           'Email: w940853815@gmail.com. '
           f'Public repos: {stats["repos"]}; contributed: {stats["contributed"]}; '
           f'stars: {stats["stars"]}; commits: {stats["commits"]}; followers: {stats["followers"]}; following: {stats["following"]}; '
           f'net lines: {stats["lines_of_code"]} ({stats["additions"]} added, {stats["deletions"]} deleted); '
           f'merged PRs: {stats["merged_prs"]}; WakaTime: {stats["wakatime"]}. Updated {stats["updated_at"]}.')
    outputs[readme], replacements = re.subn(r'<img alt="[^"]*" src="./assets/profile.svg"',
                                          lambda _: f'<img alt="{escape(alt, quote=True)}" src="./assets/profile.svg"',
                                          readme.read_text(), count=1)
    if replacements != 1:
        raise ValueError("Profile image missing from README")
    for path, content in outputs.items():
        path.write_text(content)
    data_path = ROOT / "assets" / "profile-stats.json"
    data_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    publish(collect(datetime.now(timezone.utc)))
