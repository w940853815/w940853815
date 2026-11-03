# Profile statistics

The card refreshes daily at approximately **08:17 Asia/Shanghai** with GitHub Actions. It can also be refreshed manually from the **Update profile stats** workflow. GitHub may delay scheduled runs. Only public data is published; no personal access token or WakaTime API key is required.

| Field | Definition |
| --- | --- |
| Repos | Public repositories owned by this account, including forks. |
| Contributed | Distinct public repositories outside this account with recorded commit contributions or merged authored pull requests. Commit contribution repositories are discovered year by year, starting with the account's creation year. |
| Stars | Stars received by this account's public repositories, including forks. |
| Commits | GitHub's public commit search count for `author:w940853815 is:public`, matching the previous badge. This is GitHub's search index count, not the contribution calendar. |
| Followers | Current public follower count. |
| Following | Current number of accounts followed. |
| Lines of Code | Cumulative added lines minus deleted lines in authored commits on the default branches of owned and discovered contribution repositories. Commits are deduplicated by SHA across repositories. Merge commits are excluded from line totals to avoid counting merged changes again. The green/red values show cumulative additions/deletions. |
| Merged PRs | Authored merged pull requests in currently public, accessible repositories. |
| WakaTime | Total coding duration published by the existing public WakaTime badge. |

Line totals measure **historical changes**, including non-code text files; they do not measure currently surviving code or productivity. Binary files do not contribute text line counts. Deleted/inaccessible repositories and unlinked commit identities are not included. Commits and line totals use different GitHub APIs and therefore need not match one another. Repository imports, rebases, and cherry-picks with different commit SHAs can count separately.

If any required API request fails or returns incomplete results, the workflow fails and keeps the previous published card and timestamp. The last successful data is saved in [profile-stats.json](../assets/profile-stats.json).
