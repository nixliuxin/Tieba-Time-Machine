from dataclasses import dataclass
from typing import Dict, Any, List


class ScrapeConfigKeys:
    DOWNLOAD_USER_AVATAR_MODE = "DOWNLOAD_USER_AVATAR_MODE"
    SCRAPE_SHARE_ORIGIN = "SCRAPE_SHARE_ORIGIN"
    UPDATE_SHARE_ORIGIN = "UPDATE_SHARE_ORIGIN"
    POST_FILTER_TYPE = "POST_FILTER_TYPE"


class DownloadUserAvatarMode:
    NONE = "none"
    LOW = "low"
    HIGH = "high"


class PostFilterType:
    ALL = "all"
    """ All posts + all subposts """
    AUTHOR_POSTS_WITH_SUBPOSTS = "author_posts_with_subposts"
    """ Thread author's posts + all subposts """
    AUTHOR_POSTS_WITH_AUTHOR_SUBPOSTS = "author_posts_with_author_subposts"
    """ Thread author's posts + thread author's subposts """
    AUTHOR_AND_REPLIED_POSTS_WITH_SUBPOSTS = "author_and_replied_posts_with_subposts"
    """ Thread author's posts and replied posts + all subposts """
    AUTHOR_AND_REPLIED_POSTS_WITH_AUTHOR_SUBPOSTS = "author_and_replied_posts_with_author_subposts"
    """ Thread author's posts and replied posts + thread author's subposts """


@dataclass
class ScrapeConfig:
    DOWNLOAD_USER_AVATAR_MODE: str = DownloadUserAvatarMode.HIGH

    POST_FILTER_TYPE: str = PostFilterType.ALL

    # ANCHOR scrape-only config

    SCRAPE_SHARE_ORIGIN: bool = True

    # ANCHOR scrape_update-only config

    UPDATE_SHARE_ORIGIN: bool = True

    # ONLY_APPLY_UPDATE_CONFIG_TO_NEW_BATCHES: bool = True

    # UPDATE_USER_INFO: bool = False
    """ Whether to update nickname, sign, and traffic for existing users (excludes avatar). """

    # TODO Avatar updates are special: avatars have low/high-res variants; differing download modes produce redundant data.

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> None:
        cls.POST_FILTER_TYPE = check_config_value(
            data,
            ScrapeConfigKeys.POST_FILTER_TYPE,
            [
                PostFilterType.ALL,
                PostFilterType.AUTHOR_POSTS_WITH_SUBPOSTS,
                PostFilterType.AUTHOR_POSTS_WITH_AUTHOR_SUBPOSTS,
                PostFilterType.AUTHOR_AND_REPLIED_POSTS_WITH_SUBPOSTS,
                PostFilterType.AUTHOR_AND_REPLIED_POSTS_WITH_AUTHOR_SUBPOSTS,
            ],
        )

        cls.DOWNLOAD_USER_AVATAR_MODE = check_config_value(
            data,
            ScrapeConfigKeys.DOWNLOAD_USER_AVATAR_MODE,
            [
                DownloadUserAvatarMode.NONE,
                DownloadUserAvatarMode.LOW,
                DownloadUserAvatarMode.HIGH,
            ],
        )

        cls.SCRAPE_SHARE_ORIGIN = check_config_value(
            data,
            ScrapeConfigKeys.SCRAPE_SHARE_ORIGIN,
            [True, False],
        )

        cls.UPDATE_SHARE_ORIGIN = check_config_value(
            data,
            ScrapeConfigKeys.UPDATE_SHARE_ORIGIN,
            [True, False],
        )

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        return {
            ScrapeConfigKeys.POST_FILTER_TYPE: cls.POST_FILTER_TYPE,
            ScrapeConfigKeys.DOWNLOAD_USER_AVATAR_MODE: cls.DOWNLOAD_USER_AVATAR_MODE,
            ScrapeConfigKeys.SCRAPE_SHARE_ORIGIN: cls.SCRAPE_SHARE_ORIGIN,
            ScrapeConfigKeys.UPDATE_SHARE_ORIGIN: cls.UPDATE_SHARE_ORIGIN,
        }


def check_config_value(data: Any, object_key: str, legal_values: List[Any]) -> Any:
    object_value = data.get(object_key)

    if object_value not in legal_values:
        raise ValueError(f"Value of {object_key} must be one of {legal_values}")

    return object_value
