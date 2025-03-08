import yaml
from oilprice import send_oilprice_message

if __name__ == "__main__":

    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    send_oilprice_message(config)