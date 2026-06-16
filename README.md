# 网络设备版本升级工具

一个基于 Python + PyQt5 的 Windows GUI 工具，用于批量升级网络设备版本。

## 功能

1. **SSH 登录跳板机**：通过界面输入跳板机 IP、端口、用户名、密码。
2. **Telnet 登录网络设备**：在跳板机上通过 Telnet 登录目标网络设备。
3. **执行升级命令**：在网络设备上批量执行用户自定义的升级命令。
4. **Excel 导入设备**：支持从 Excel 文件导入网络设备的 IP、用户名、密码。
5. **命令变量替换**：升级命令中可使用 `{device_ip}`、`{jump_host}` 等变量，批量执行时自动替换。
6. **日志输出**：实时显示每台设备的升级过程和结果。

## 项目结构

```
update_cpe/
├── main.py                  # 程序入口
├── requirements.txt         # 依赖包
├── README.md                # 说明文档
├── core/
│   ├── ssh_client.py        # SSH 客户端与 Telnet 交互封装
│   ├── excel_reader.py      # Excel 读取模块
│   └── device_upgrader.py   # 设备升级核心逻辑
├── gui/
│   └── main_window.py       # PyQt5 主窗口
└── examples/
    └── create_sample_excel.py  # 生成示例 Excel 脚本
```

## 环境要求

- Python 3.8+
- Windows 操作系统（也支持 Linux/macOS，但主要针对 Windows 打包）

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行程序

```bash
python main.py
```

## 使用说明

### 1. 准备 Excel 文件

Excel 文件需要包含以下列（列名不区分大小写，支持中英文）：

| IP       | Username | Password |
|----------|----------|----------|
| 10.0.0.1 | admin    | admin123 |
| 10.0.0.2 | admin    | admin123 |

支持的列名别名：
- **IP**：`ip`, `IP`, `设备IP`, `设备地址`, `ip地址`, `address`, `addr`
- **Username**：`username`, `Username`, `用户名`, `账号`, `user`, `账户`
- **Password**：`password`, `Password`, `密码`, `口令`, `passwd`, `pwd`

可以运行 `python examples/create_sample_excel.py` 生成一个示例 Excel 文件。

### 2. 配置跳板机

在软件界面顶部输入跳板机的：
- IP 地址
- SSH 端口（默认 22）
- 用户名
- 密码

### 3. 填写升级命令

在"升级命令"文本框中，每行输入一条命令。例如：

```
system-view
ftp 192.168.10.100
admin
admin123
binary
get Vxxx.cc
bye
boot-loader file flash:/Vxxx.cc main
reboot
```

**支持变量替换**：

| 变量 | 含义 |
|------|------|
| `{device_ip}` | 当前设备的 IP 地址 |
| `{jump_host}` | 跳板机 IP 地址 |

如果留空，则默认执行 `display version`（仅用于测试连通性）。

### 4. 导入设备并升级

1. 点击"导入 Excel"按钮，选择准备好的 Excel 文件。
2. 确认设备列表显示正确。
3. 点击"开始升级"按钮。
4. 查看下方日志区域的实时输出。
5. 升级完成后会弹出汇总提示。

## 打包为 Windows 可执行文件（可选）

使用 PyInstaller 打包为单文件 EXE：

```bash
pip install pyinstaller
pyinstaller -F -w -n "网络设备升级工具" main.py
```

打包后的可执行文件位于 `dist/网络设备升级工具.exe`。

## 注意事项

1. **跳板机权限**：确保跳板机允许通过 SSH 登录，并且支持从跳板机 Telnet 到目标网络设备。
2. **Telnet 端口**：默认使用 23 端口，如需修改请在代码中调整。
3. **命令超时**：默认单条命令超时时间为 180 秒，可在 `device_upgrader.py` 中调整。
4. **线程安全**：升级过程在后台线程执行，不会阻塞 GUI，可随时点击"停止"按钮终止。
5. **异常处理**：如果某台设备升级失败，程序会继续处理下一台设备（可在代码中配置遇到错误即停止）。

## 常见问题

### Q: 连接跳板机失败？
A: 检查 IP、端口、用户名、密码是否正确；确认防火墙未拦截 SSH 端口。

### Q: Telnet 登录设备失败？
A: 确认跳板机可以访问目标设备的 Telnet 端口；检查设备是否启用了 Telnet 服务。

### Q: 命令执行超时？
A: 某些升级命令（如文件传输、重启）耗时较长，可在 `device_upgrader.py` 中增大 `timeout` 参数。

## License

MIT
