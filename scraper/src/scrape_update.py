import asyncio

from modules.scrape_update_module import scrape_update


def main():
    path = input("Enter the path to the local thread data: ")
    asyncio.run(scrape_update(path))


if __name__ == "__main__":
    main()
