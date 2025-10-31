import yaml
import os

def load_config():
    """加载配置文件"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, 'config.yml')

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def backtest_param():
    config = load_config()
    backtest_params = config.get('backtest_params', {})

    return backtest_params