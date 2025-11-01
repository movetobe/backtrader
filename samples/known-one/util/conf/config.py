import yaml
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'config.yml')

_config = None


def load_config():
    global _config
    if _config is not None:
        return _config

    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Configuration file not found at {CONFIG_PATH}")

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        _config = yaml.safe_load(f) or {}

    return _config


def backtest_param():
    config = load_config()
    params = config.get('backtest_params')
    if not params:
        raise RuntimeError("Missing required config field 'backtest_params'")
    try:
        return {
            'beg': str(params['beg']),
            'end': str(params['end']),
            'init_cash': float(params.get('init_cash', 100000.00)),
            'klt': int(params.get('klt', 102)),
            'fqt': int(params.get('fqt', 1))
        }
    except (ValueError, TypeError) as e:
        raise RuntimeError(f"Invalid parameter format: {str(e)}")


def stock_file_list():
    config = load_config()
    data_source = config.get("data_source", {})
    data_dir = os.path.join(PROJECT_ROOT, data_source.get('data_dir', 'data/'))
    files = data_source.get('stock_file_list')
    if not files:
        raise RuntimeError("Missing required field 'stock_file_list' in 'data_source'")
    return [os.path.join(data_dir, f) for f in files]


def logging():
    config = load_config()
    log_cfg = config.get('logging', {})
    return {
        'path': os.path.join(PROJECT_ROOT, log_cfg.get('path', 'logs/')),
        'level': log_cfg.get('level', 'INFO'),
        'max_size': log_cfg.get('max_size', 5 * 1024 * 1024),  # 5MB
        'backup_count': log_cfg.get('backup_count', 5)
    }


def output_dir():
    config = load_config()
    return os.path.join(
        PROJECT_ROOT,
        config.get('output', {}).get('reports_dir', 'data/reports/')
    )
