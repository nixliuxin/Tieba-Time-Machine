import asyncio
import os
import sys
from enum import IntEnum, auto

import orjson
import questionary

from modules.scrape_module import scrape
from modules.scrape_update_module import scrape_update
from scrape_config import DownloadUserAvatarMode, ScrapeConfig, ScrapeConfigKeys, PostFilterType
from tieba_auth import TiebaAuth
from utils.cli_questionary import InfoStyle
from utils.common import counter_gen, json_dumps
from utils.msg_printer import PrintColor

counter = counter_gen()
next(counter)  # Prime the generator

TIEBA_AUTH_FILENAME = "tieba_auth.json"


def read_tieba_auth() -> None:
    tieba_auth_file_path = os.path.join(os.getcwd(), TIEBA_AUTH_FILENAME)

    try:
        with open(tieba_auth_file_path, "r", encoding="utf-8") as f:
            TiebaAuth.from_dict(orjson.loads(f.read()))
    except Exception:
        BDUSS = questionary.text("BDUSS not configured. Please enter it: ").ask()
        TiebaAuth.BDUSS = BDUSS
        with open(tieba_auth_file_path, "w", encoding="utf-8") as f:
            f.write(json_dumps(TiebaAuth.to_dict()))


SCRAPE_CONFIG_FILENAME = "scrape_config.json"
scrape_config_file_path = os.path.join(os.getcwd(), SCRAPE_CONFIG_FILENAME)


def read_scrape_config() -> None:
    try:
        with open(scrape_config_file_path, "r", encoding="utf-8") as f:
            ScrapeConfig.from_dict(orjson.loads(f.read()))
    except FileNotFoundError:
        if questionary.confirm("Config file not found. Use defaults and generate a new file?").ask():
            write_scrape_config()
        else:
            sys.exit()
    except orjson.JSONDecodeError:
        if questionary.confirm("Config file has invalid JSON. Use defaults and regenerate?").ask():
            write_scrape_config()
        else:
            sys.exit()
    except ValueError as err:
        if questionary.confirm(f"Config value error: {str(err)}. Use defaults and regenerate?").ask():
            write_scrape_config()
        else:
            sys.exit()


def write_scrape_config() -> None:
    with open(scrape_config_file_path, "w", encoding="utf-8") as f:
        f.write(json_dumps(ScrapeConfig.to_dict()))


def set_scrape_config() -> None:
    counter.send((0, 1))
    set_scrape_config_choice = [
        questionary.Choice(
            f"{next(counter)}. Post filter ({ScrapeConfigKeys.POST_FILTER_TYPE})",
            ScrapeConfigKeys.POST_FILTER_TYPE,
        ),
        questionary.Choice(
            f"{next(counter)}. Avatar download mode ({ScrapeConfigKeys.DOWNLOAD_USER_AVATAR_MODE})",
            ScrapeConfigKeys.DOWNLOAD_USER_AVATAR_MODE,
        ),
        questionary.Choice(
            f"{next(counter)}. Scrape shared originals ({ScrapeConfigKeys.SCRAPE_SHARE_ORIGIN})",
            ScrapeConfigKeys.SCRAPE_SHARE_ORIGIN,
        ),
        questionary.Choice(
            f"{next(counter)}. Update shared originals ({ScrapeConfigKeys.UPDATE_SHARE_ORIGIN})",
            ScrapeConfigKeys.UPDATE_SHARE_ORIGIN,
        ),
        questionary.Choice(
            f"{next(counter)}. Exit",
            "exit",
        ),
    ]

    while True:
        scrape_config_key = questionary.select("Select config option", choices=set_scrape_config_choice).ask()
        if ScrapeConfigKeys.POST_FILTER_TYPE == scrape_config_key:
            counter.send((0, 1))
            post_filter_type_choices = [
                questionary.Choice(
                    f"{next(counter)}. All posts + all subposts ({PostFilterType.ALL})",
                    PostFilterType.ALL,
                ),
                questionary.Choice(
                    f"{next(counter)}. Author posts + all subposts ({PostFilterType.AUTHOR_POSTS_WITH_SUBPOSTS})",
                    PostFilterType.AUTHOR_POSTS_WITH_SUBPOSTS,
                ),
                questionary.Choice(
                    f"{next(counter)}. Author posts + author subposts ({PostFilterType.AUTHOR_POSTS_WITH_AUTHOR_SUBPOSTS})",
                    PostFilterType.AUTHOR_POSTS_WITH_AUTHOR_SUBPOSTS,
                ),
                questionary.Choice(
                    f"{next(counter)}. Author + replied posts + all subposts ({PostFilterType.AUTHOR_AND_REPLIED_POSTS_WITH_SUBPOSTS})",
                    PostFilterType.AUTHOR_AND_REPLIED_POSTS_WITH_SUBPOSTS,
                ),
                questionary.Choice(
                    f"{next(counter)}. Author + replied posts + author subposts ({PostFilterType.AUTHOR_AND_REPLIED_POSTS_WITH_AUTHOR_SUBPOSTS})",
                    PostFilterType.AUTHOR_AND_REPLIED_POSTS_WITH_AUTHOR_SUBPOSTS,
                ),
            ]
            post_filter_type = questionary.select("Select post filter mode", choices=post_filter_type_choices).ask()
            ScrapeConfig.POST_FILTER_TYPE = post_filter_type
            write_scrape_config()
        elif ScrapeConfigKeys.DOWNLOAD_USER_AVATAR_MODE == scrape_config_key:
            counter.send((0, 1))
            download_user_avatar_mode_choices = [
                questionary.Choice(
                    f"{next(counter)}. Don't save ({DownloadUserAvatarMode.NONE})", DownloadUserAvatarMode.NONE
                ),
                questionary.Choice(
                    f"{next(counter)}. Save low-res ({DownloadUserAvatarMode.LOW})", DownloadUserAvatarMode.LOW
                ),
                questionary.Choice(
                    f"{next(counter)}. Save high-res ({DownloadUserAvatarMode.HIGH})", DownloadUserAvatarMode.HIGH
                ),
            ]
            download_user_avatar_mode = questionary.select(
                "Select avatar download mode", choices=download_user_avatar_mode_choices
            ).ask()
            ScrapeConfig.DOWNLOAD_USER_AVATAR_MODE = download_user_avatar_mode
            write_scrape_config()
        elif ScrapeConfigKeys.SCRAPE_SHARE_ORIGIN == scrape_config_key:
            scrape_share_origin = questionary.confirm("Scrape shared original posts?").ask()
            ScrapeConfig.SCRAPE_SHARE_ORIGIN = scrape_share_origin
            write_scrape_config()
        elif ScrapeConfigKeys.UPDATE_SHARE_ORIGIN == scrape_config_key:
            update_share_origin = questionary.confirm("Update shared original posts?").ask()
            ScrapeConfig.UPDATE_SHARE_ORIGIN = update_share_origin
            write_scrape_config()
        elif "exit" == scrape_config_key:
            break


class ProgramFeatures(IntEnum):
    SCRAPE = auto()
    SCRAPE_UPDATE = auto()
    EXPORT_TO_READABLE = auto()
    MODIFY_SCRAPE_CONFIG = auto()


def main():
    counter.send((0, 1))

    features_choices = [
        questionary.Choice(
            f"{next(counter)}. Scrape thread",
            ProgramFeatures.SCRAPE,
        ),
        questionary.Choice(
            f"{next(counter)}. Update local thread data",
            ProgramFeatures.SCRAPE_UPDATE,
        ),
        questionary.Choice(
            f"{next(counter)}. Export to readable format (not implemented)",
            ProgramFeatures.EXPORT_TO_READABLE,
        ),
        questionary.Choice(
            f"{next(counter)}. Modify scrape config",
            ProgramFeatures.MODIFY_SCRAPE_CONFIG,
        ),
    ]
    while True:
        selected_features = questionary.select("Select feature", choices=features_choices, style=InfoStyle).ask()

        if ProgramFeatures.SCRAPE == selected_features:
            try:
                read_tieba_auth()
                read_scrape_config()
                tid = int(questionary.text("Enter the tid of the thread to scrape: ").ask())
                asyncio.run(scrape(tid))
            except ValueError:
                print(f"{PrintColor.RED}tid must be an integer{PrintColor.RESET}")
        elif ProgramFeatures.SCRAPE_UPDATE == selected_features:
            read_tieba_auth()
            read_scrape_config()
            path = input("Enter the path to local thread data: ")
            asyncio.run(scrape_update(path))
        elif ProgramFeatures.EXPORT_TO_READABLE == selected_features:
            print(f"{PrintColor.RED}This feature is not yet implemented{PrintColor.RESET}")
        elif ProgramFeatures.MODIFY_SCRAPE_CONFIG == selected_features:
            set_scrape_config()


if __name__ == "__main__":
    main()
