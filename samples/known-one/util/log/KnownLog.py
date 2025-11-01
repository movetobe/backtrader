import os
import inspect
import util.conf.config as config


class KnownLog:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, filename=None, filedir="../../log/"):
        if filename:
            self.init(filename, filedir)

    def init(self, filename="backtrade_result.txt"):
        log_path = config.logging()['path']
        os.makedirs(log_path, exist_ok=True)
        self.file_path = os.path.join(log_path, filename)
        if os.path.exists(self.file_path):
            self.clear()

    def write(self, txt, dt=None):
        # dt可以是datetime对象或字符串
        if dt is not None:
            if hasattr(dt, 'isoformat'):
                dt_str = dt.isoformat()
            else:
                dt_str = str(dt)
        else:
            dt_str = ''

        # 获取调用者信息
        stack_info = inspect.stack()[1]  # 第0层是当前函数，第1层是调用者
        file_name = os.path.basename(stack_info.filename)
        line_number = stack_info.lineno

        # 格式化输出
        log_line = f"[{file_name}:{line_number}] {dt_str} {txt}\n"

        with open(self.file_path, 'a', encoding='utf-8') as f:
            f.write(log_line)

    def clear(self):
        with open(self.file_path, 'w', encoding='utf-8') as f:
            pass  # 写入空内容，文件即被清空


logger = KnownLog()