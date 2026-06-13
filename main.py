import argparse

from wildmagic.ui import run_game


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Launch the Wild Magic graphical UI.")
    parser.add_argument(
        "--autoplay",
        action="store_true",
        help="Start the pygame UI with AI watch mode already enabled.",
    )
    args = parser.parse_args()
    run_game(autoplay=args.autoplay)
