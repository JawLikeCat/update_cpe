"""
生成示例 Excel 文件，用于测试设备导入功能。
"""
import os
import sys

# 将项目根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import pandas as pd
except ImportError:
    print("请先安装 pandas: pip install pandas openpyxl")
    sys.exit(1)


def create_sample(filepath: str = "sample_devices.xlsx"):
    data = {
        "设备IP": ["192.168.1.1", "192.168.1.2", "192.168.1.3"],
        "用户名": ["admin", "admin", "root"],
        "密码": ["admin123", "admin456", "root123"],
    }
    df = pd.DataFrame(data)
    df.to_excel(filepath, index=False, engine="openpyxl")
    print(f"示例 Excel 已生成: {os.path.abspath(filepath)}")
    print("内容预览:")
    print(df.to_string(index=False))


if __name__ == "__main__":
    create_sample()
