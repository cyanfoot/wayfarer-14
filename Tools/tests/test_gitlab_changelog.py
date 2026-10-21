"""Offline tests for GitLab changelog history and Discord dispatch."""

import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import requests


SCRIPT = Path(__file__).resolve().parents[1] / "actions_changelogs_since_last_run.py"
SPEC = importlib.util.spec_from_file_location("changelog", SCRIPT)
changelog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(changelog)


class GitLabChangelogTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            "GITLAB_CI": "true",
            "CI_API_V4_URL": "https://gitlab.example/api/v4",
            "CI_PROJECT_ID": "42",
            "CI_JOB_ID": "100",
            "CI_JOB_NAME": "publish_changelog",
            "CI_COMMIT_REF_NAME": "master",
            "CHANGELOG_GITLAB_TOKEN": "test-token",
        }, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.session = Mock()
        self.session.headers = {}
        factory = patch.object(changelog.requests, "Session", return_value=self.session)
        factory.start()
        self.addCleanup(factory.stop)

    @staticmethod
    def response(jobs=None, next_page="", text="Entries: []"):
        response = Mock()
        response.json.return_value = jobs or []
        response.headers = {"X-Next-Page": next_page}
        response.text = text
        return response

    @staticmethod
    def job(job_id=90, name="publish_changelog", ref="master", tag=False):
        return {"id": job_id, "name": name, "ref": ref, "tag": tag,
                "commit": {"id": "previous-sha"}}

    def test_paginates_and_filters_unrelated_jobs(self):
        self.session.get.side_effect = [
            self.response([
                self.job(110), self.job(100), self.job(99, name="publish_cdn"),
                self.job(98, ref="staging"), self.job(97, tag=True),
            ], next_page="2"),
            self.response([self.job()]),
            self.response(text="Entries: [old]"),
        ]
        self.assertEqual(changelog.get_last_gitlab_changelog(), "Entries: [old]")
        calls = self.session.get.call_args_list
        self.assertEqual(calls[1].kwargs["params"]["page"], "2")
        self.assertEqual(calls[2].kwargs["params"], {"ref": "previous-sha"})
        self.assertIn("Resources%2FChangelog%2FWayfarer.yml/raw", calls[2].args[0])
        self.assertEqual(self.session.headers["PRIVATE-TOKEN"], "test-token")

    def test_first_run_uses_current_file_without_history_replay(self):
        self.session.get.return_value = self.response()
        with patch.object(changelog.Path, "read_text", return_value="Entries: [current]"):
            self.assertEqual(changelog.get_last_gitlab_changelog(), "Entries: [current]")
        self.assertEqual(self.session.get.call_count, 1)

    def test_explicit_baseline_does_not_query_jobs(self):
        os.environ["CHANGELOG_BASE_SHA"] = "migration-sha"
        self.session.get.return_value = self.response(text="Entries: [baseline]")
        self.assertEqual(changelog.get_last_gitlab_changelog(), "Entries: [baseline]")
        self.session.get.assert_called_once()
        self.assertEqual(self.session.get.call_args.kwargs["params"], {"ref": "migration-sha"})

    def test_missing_token_fails_before_api_access(self):
        del os.environ["CHANGELOG_GITLAB_TOKEN"]
        with self.assertRaisesRegex(RuntimeError, "CHANGELOG_GITLAB_TOKEN"):
            changelog.get_last_gitlab_changelog()
        self.session.get.assert_not_called()

    def test_missing_history_file_fails_closed(self):
        missing_file = self.response()
        missing_file.raise_for_status.side_effect = requests.HTTPError("404")
        self.session.get.side_effect = [self.response([self.job()]), missing_file]
        with self.assertRaises(requests.HTTPError):
            changelog.get_last_gitlab_changelog()

    def test_api_permission_failure_is_not_treated_as_first_run(self):
        response = self.response()
        response.raise_for_status.side_effect = requests.HTTPError("403")
        self.session.get.return_value = response
        with self.assertRaises(requests.HTTPError):
            changelog.get_last_gitlab_changelog()

    def test_main_sends_only_new_entries_without_network(self):
        current = {"Entries": [
            {"id": 1, "author": "Old", "changes": []},
            {"id": 2, "author": "New", "changes": [{"type": "Fix", "message": "Fixed it"}]},
        ]}
        with (patch.object(changelog, "DISCORD_WEBHOOK_URL", "test-webhook"),
              patch.object(changelog, "get_last_gitlab_changelog", return_value="Entries: [{id: 1}]"),
              patch("builtins.open", unittest.mock.mock_open(read_data=changelog.yaml.safe_dump(current))),
              patch.object(changelog, "send_message_lines") as send):
            changelog.main()
        message = "".join(send.call_args.args[0])
        self.assertIn("Fixed it", message)
        self.assertNotIn("Old", message)
        self.assertEqual(changelog.get_discord_body(message)["allowed_mentions"], {"parse": []})

    def test_missing_webhook_skips_api_access(self):
        with patch.object(changelog, "DISCORD_WEBHOOK_URL", None):
            changelog.main()
        self.session.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()