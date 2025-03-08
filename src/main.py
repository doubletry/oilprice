import argparse

import yaml

from oilprice import send_oilprice_message


def parse_args():
    parser = argparse.ArgumentParser(description="Send oil price message")
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="config.yaml",
        help="Config file path",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    with open(args.config, "r") as f:
        config = yaml.safe_load(f)

    send_oilprice_message(config)
