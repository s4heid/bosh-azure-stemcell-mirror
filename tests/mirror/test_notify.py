import unittest
from unittest.mock import MagicMock, patch

from src.mirror.notify import GitHubNotifier, GitHubNotifierConfig, NotificationError


class TestGitHubNotifier(unittest.TestCase):
    def setUp(self) -> None:
        self.config = GitHubNotifierConfig(
            api_base_url="https://api.github.com",
            repository_owner="example",
            repository_name="repo",
            workflow_identifier="sync.yml",
            ref="main",
            token="ghs_example",
            timeout_seconds=5,
        )
        self.notifier = GitHubNotifier(self.config)

    @patch("src.mirror.notify.requests.post")
    def test_notify_success(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        self.notifier.notify_new_stemcell(
            {
                "gallery_name": "gallery",
                "gallery_image_name": "image",
                "gallery_image_version": "1.2.3",
                "gallery_subscription_id": "12345678-1234-5678-1234-567812345678",
                "gallery_resource_group": "test-gallery-rg",
            },
        )

        mock_post.assert_called_once()
        called_kwargs = mock_post.call_args.kwargs
        self.assertEqual(called_kwargs["json"]["ref"], "main")
        self.assertEqual(called_kwargs["json"]["inputs"]["gallery_name"], "gallery")
        self.assertEqual(called_kwargs["json"]["inputs"]["gallery_image_version"], "1.2.3")
        self.assertEqual(
            called_kwargs["json"]["inputs"]["gallery_subscription_id"],
            "12345678-1234-5678-1234-567812345678",
        )
        self.assertEqual(
            called_kwargs["json"]["inputs"]["gallery_resource_group"],
            "test-gallery-rg",
        )

    @patch("src.mirror.notify.requests.post")
    def test_notify_failure_raises(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "server error"
        mock_post.return_value = mock_response

        with self.assertRaises(NotificationError):
            self.notifier.notify_new_stemcell({})

        mock_post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
