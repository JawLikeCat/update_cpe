import pandas as pd
from typing import List, Dict


def read_devices_from_excel(filepath: str) -> List[Dict[str, str]]:
    """
    从 Excel 文件中读取网络设备信息。

    期望的列名（不区分大小写，支持中英文列名）:
        - IP / ip / 设备IP / 设备地址
        - Username / username / 用户名 / 账号
        - Password / password / 密码 / 口令

    返回:
        设备字典列表，每个字典包含 ip, username, password。
    """
    try:
        df = pd.read_excel(filepath, engine="openpyxl")
    except Exception as e:
        raise ValueError(f"读取 Excel 失败: {e}")

    if df.empty:
        raise ValueError("Excel 文件为空或没有数据")

    # 列名映射：标准化为内部字段名
    column_map = {
        "ip": ["ip", "IP", "设备IP", "设备地址", "ip地址", "address", "addr"],
        "username": ["username", "Username", "用户名", "账号", "user", "账户"],
        "password": ["password", "Password", "密码", "口令", "passwd", "pwd"],
    }

    result_columns = {}
    for standard, aliases in column_map.items():
        for col in df.columns:
            if col in aliases:
                result_columns[standard] = col
                break

    missing = [k for k in column_map if k not in result_columns]
    if missing:
        available = ", ".join(str(c) for c in df.columns)
        raise ValueError(
            f"Excel 缺少必要列 {missing}。当前可用列: {available}"
        )

    devices = []
    for _, row in df.iterrows():
        ip = str(row[result_columns["ip"]]).strip()
        username = str(row[result_columns["username"]]).strip()
        password = str(row[result_columns["password"]]).strip()

        if not ip or ip.lower() == "nan":
            continue

        devices.append(
            {
                "ip": ip,
                "username": username,
                "password": password,
            }
        )

    return devices
