import asyncio

from modules.scrape_module import scrape


def main():
    tid = int(input("Enter the tid of the thread to scrape: "))
    asyncio.run(scrape(tid))


if __name__ == "__main__":
    main()
