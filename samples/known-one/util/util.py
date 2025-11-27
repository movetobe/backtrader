import os
from util.log.KnownLog import logger
def get_stock_list(file):
    if not os.path.exists(file):
        logger.write(f"file not exist:{file}\n")
        return []

    stock_list = []
    with open(file, 'r', encoding='utf-8') as f:
        for line in f:
            # 移除注释和空白
            code = line.split('#')[0].strip()
            if not code:
                continue
            stock_list.append(code)
    return stock_list