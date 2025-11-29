import os
import datetime


def get_stock_list(file):
    if not os.path.exists(file):
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


def rename_file(file_path):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_path, ext = os.path.splitext(file_path)
    new_path = f"{base_path}_{timestamp}{ext}"
    os.rename(file_path, new_path)
