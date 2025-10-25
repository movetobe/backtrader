import os

class KnownLog:
    def __init__(self, filename='backtest_results.txt'):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.file_path = os.path.join(current_dir, filename)

    def write(self, txt, dt=None):
        # dt可以是datetime对象或字符串
        if dt is not None:
            if hasattr(dt, 'isoformat'):
                dt_str = dt.isoformat()
            else:
                dt_str = str(dt)
        else:
            dt_str = ''
        with open(self.file_path, 'a', encoding='utf-8') as f:
            f.write(f"{dt_str} {txt}\n")

    def clear(self):
        with open(self.file_path, 'w', encoding='utf-8') as f:
            pass  # 写入空内容，文件即被清空