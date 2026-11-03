import unittest
from datetime import datetime, timezone
from io import BytesIO
import xml.etree.ElementTree as ET
from unittest.mock import patch

from scripts import profile_stats as stats


class ProfileStatsTests(unittest.TestCase):
    def test_lines_deduplicate_forks_and_exclude_merge_diffs(self):
        commit = {"oid": "a", "additions": 20, "deletions": 3, "parents": {"totalCount": 1}}
        merge = {"oid": "b", "additions": 200, "deletions": 30, "parents": {"totalCount": 2}}
        root = {"oid": "c", "additions": 5, "deletions": 0, "parents": {"totalCount": 0}}
        self.assertEqual(stats.commit_totals([commit, commit, merge, root]), (25, 3))

    def test_connection_fetches_every_page(self):
        pages = [{"nodes": [1], "pageInfo": {"hasNextPage": True, "endCursor": "next"}},
                 {"nodes": [2], "pageInfo": {"hasNextPage": False, "endCursor": None}}]
        with patch.object(stats, "graphql", side_effect=[{"user": {"repos": page}} for page in pages]) as call:
            self.assertEqual(list(stats.connection("query", "repos")), [1, 2])
            self.assertEqual(call.call_args.kwargs["after"], "next")

    def test_private_repository_never_contributes_lines(self):
        with patch.object(stats, "graphql", return_value={"repository": {"isPrivate": True, "isEmpty": False}}):
            self.assertEqual(list(stats.repository_commits("someone/private", "user-id")), [])

    def test_wakatime_shadow_text_is_not_double_counted(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><text>wakatime</text><text>885 hrs 3 mins</text><text>885 hrs 3 mins</text></svg>'
        self.assertEqual(stats.parse_wakatime(svg), "885 hrs 3 mins")
        with self.assertRaises(ValueError):
            stats.parse_wakatime('<svg xmlns="http://www.w3.org/2000/svg"><text>unavailable</text></svg>')

    def test_collection_publishes_only_public_metrics(self):
        owned = {"nameWithOwner": "w940853815/public", "isPrivate": False, "stargazerCount": 9}
        hidden = {"nameWithOwner": "w940853815/private", "isPrivate": True, "stargazerCount": 999}
        external = {"nameWithOwner": "org/public", "isPrivate": False}
        badge = b'<svg xmlns="http://www.w3.org/2000/svg"><text>10 hrs 2 mins</text></svg>'
        user = {"id": "user-id", "createdAt": "2016-03-10", "followers": {"totalCount": 5}, "following": {"totalCount": 3}}
        collection = {"totalRepositoriesWithContributedCommits": 2,
                      "commitContributionsByRepository": [{"repository": external}, {"repository": hidden}]}
        with patch.object(stats, "graphql", side_effect=[{"user": user}, {"user": {"contributionsCollection": collection}}]), \
             patch.object(stats, "connection", side_effect=[[owned, hidden], [{"repository": external}, {"repository": hidden}]]), \
             patch.object(stats, "repository_commits", return_value=[]) as history, \
             patch.object(stats, "api", return_value={"total_count": 7, "incomplete_results": False}), \
             patch.object(stats.urllib.request, "urlopen", return_value=BytesIO(badge)):
            result = stats.collect(datetime(2016, 12, 1, tzinfo=timezone.utc))
        self.assertEqual((result["repos"], result["contributed"], result["stars"], result["merged_prs"]), (1, 1, 9, 1))
        self.assertEqual({call.args[0] for call in history.call_args_list}, {"w940853815/public", "org/public"})
        self.assertNotIn("private", str(result))

    def test_render_is_idempotent_and_preserves_introduction(self):
        data = dict(repos=106, contributed=14, stars=21, commits=4746, followers=17, following=83,
                    additions=1234567, deletions=234567, lines_of_code=1000000,
                    merged_prs=44, wakatime="885 hrs 3 mins", updated_at="2026-11-03 08:17 CST")
        for mobile in (False, True):
            for dark in (False, True):
                name = "profile" + ("-mobile" if mobile else "") + ("-dark" if dark else "") + ".svg"
                source = (stats.ROOT / "assets" / name).read_text()
                result = stats.render_card(source, data, mobile, dark)
                self.assertEqual(stats.render_card(result, data, mobile, dark), result)
                self.assertIn("w940853815@gmail.com", result)
                self.assertIn("885 hrs 3 mins", result)
                self.assertEqual(result.count('id="profile-stats"'), 1)
                ET.fromstring(result)
        with patch("pathlib.Path.write_text") as write:
            stats.publish(data)
        readme = next(call.args[0] for call in write.call_args_list if "<picture>" in call.args[0])
        self.assertIn("wrd (w940853815)", readme)
        self.assertIn("Email: w940853815@gmail.com", readme)
        self.assertIn("Project stack: Python, Django, Go, Vue, JavaScript, TypeScript", readme)


if __name__ == "__main__":
    unittest.main()
