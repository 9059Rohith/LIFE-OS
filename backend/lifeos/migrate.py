from .config import Settings
from .store import Database


def main():
    db = Database(Settings().database_url)
    db.engine.dispose()
    print("LIFEOS schema revision 1 is ready")


if __name__ == "__main__":
    main()
