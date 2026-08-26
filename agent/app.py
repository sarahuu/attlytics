import sys


def main():
    if "--agent" in sys.argv:
        from agent.main import run as run_agent

        run_agent()
    else:
        from agent.tray import run_app

        run_app()


if __name__ == "__main__":
    main()
