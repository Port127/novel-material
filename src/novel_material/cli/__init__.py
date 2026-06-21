"""CLI 模块入口，避免包初始化时提前加载命令注册模块。"""


def main():
    """延迟导入 CLI 主函数，兼容 console_scripts 与 ``python -m``。"""
    from .main import main as run_main

    return run_main()


__all__ = ["main"]
