import yaml
import os

_config = None


def load_config(filedir="../../config.yml"):
    global _config
    if _config is not None:
        return _config

    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, filedir)

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        _config = yaml.safe_load(f)

    return _config


def backtest_param():
    config = load_config()
    return config.get('backtest_params', {})


def stock_file_list():
    config = load_config()
    return config.get('stock_file_list', [])
