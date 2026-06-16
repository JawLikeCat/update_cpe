import re
import time
import socket
import paramiko
from typing import Optional, List, Tuple


class SSHClient:
    """SSH 客户端，用于连接跳板机并在跳板机上执行 Telnet 操作。"""

    def __init__(self):
        self.ssh: Optional[paramiko.SSHClient] = None
        self.channel: Optional[paramiko.Channel] = None
        self.buffer: str = ""

    def connect(
        self,
        hostname: str,
        port: int = 22,
        username: str = "",
        password: str = "",
        timeout: int = 30,
    ) -> bool:
        """建立到跳板机的 SSH 连接并打开交互式通道。"""
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(
                hostname=hostname,
                port=port,
                username=username,
                password=password,
                timeout=timeout,
                look_for_keys=False,
                allow_agent=False,
            )
            # 打开交互式通道，模拟终端
            self.channel = self.ssh.invoke_shell(term="vt100", width=200, height=50)
            time.sleep(0.5)
            self._drain_buffer()
            return True
        except Exception as e:
            raise ConnectionError(f"SSH 连接失败: {e}")

    def disconnect(self):
        """关闭 SSH 连接。"""
        if self.channel:
            self.channel.close()
            self.channel = None
        if self.ssh:
            self.ssh.close()
            self.ssh = None
        self.buffer = ""

    def is_connected(self) -> bool:
        """检查连接是否仍然存活。"""
        if not self.channel:
            return False
        return not self.channel.closed

    def _read_available(self, timeout: float = 0.5) -> str:
        """读取通道中当前可用的所有数据（带短暂等待）。"""
        output = ""
        if not self.channel:
            return output
        start = time.time()
        while time.time() - start < timeout:
            if self.channel.recv_ready():
                chunk = self.channel.recv(4096)
                if chunk:
                    try:
                        output += chunk.decode("utf-8", errors="replace")
                    except UnicodeDecodeError:
                        output += chunk.decode("gbk", errors="replace")
                else:
                    break
            else:
                # 没有数据时短暂休眠，避免 CPU 空转
                time.sleep(0.05)
        return output

    def _drain_buffer(self) -> str:
        """清空并返回缓冲区内容。"""
        data = self._read_available(timeout=1.0)
        self.buffer += data
        return data

    def send_command(self, command: str, add_newline: bool = True):
        """发送命令到通道。"""
        if not self.channel:
            raise RuntimeError("SSH 通道未建立")
        cmd = command + ("\r" if add_newline else "")
        self.channel.send(cmd.encode("utf-8"))

    def expect(
        self,
        patterns: List[str],
        timeout: int = 30,
        strip_ansi: bool = True,
    ) -> Tuple[int, str]:
        """
        等待输出匹配给定正则表达式列表之一。
        自动处理网络设备常见的 --More-- 分页提示。

        返回:
            (匹配到的模式索引, 捕获到的完整输出)
        """
        if not self.channel:
            raise RuntimeError("SSH 通道未建立")

        compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
        # 分页提示正则（覆盖常见中英文及变体）
        more_patterns = re.compile(
            r"(--More--|---- More ----|Press any key to continue|\(q\)uit|q\)uit|---- 更多 ----| 更多 )",
            re.IGNORECASE,
        )

        output = self.buffer
        start_time = time.time()
        more_count = 0
        max_more = 200  # 防止无限翻页

        while time.time() - start_time < timeout:
            # 先尝试用当前 buffer 匹配
            text = self._strip_ansi(output) if strip_ansi else output

            # 检查目标模式
            for idx, pattern in enumerate(compiled):
                match = pattern.search(text)
                if match:
                    self.buffer = ""
                    return idx, text

            # 检查分页提示，自动发送空格翻页
            if more_patterns.search(text):
                more_count += 1
                if more_count > max_more:
                    self.buffer = ""
                    raise TimeoutError(
                        f"分页翻页次数超过限制 ({max_more})\n当前输出:\n{output}"
                    )
                self.channel.send(b" ")
                time.sleep(0.3)
                chunk = self._read_available(timeout=1.0)
                output += chunk
                continue

            # 读取新数据
            if self.channel.recv_ready():
                chunk = self._read_available(timeout=0.5)
                output += chunk
            elif self.channel.closed:
                break
            else:
                time.sleep(0.1)

        self.buffer = ""
        raise TimeoutError(f"等待模式超时 ({timeout}s): {patterns}\n当前输出:\n{output}")

    @staticmethod
    def _strip_ansi(text: str) -> str:
        """去除 ANSI 转义序列。"""
        ansi_escape = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")
        return ansi_escape.sub("", text)


class JumpHostTelnet:
    """封装在跳板机上通过 Telnet 登录网络设备的交互。"""

    def __init__(self, ssh_client: SSHClient):
        self.ssh = ssh_client
        self.prompt_patterns = [
            r">\s*$",          # 用户模式提示符
            r"#\s*$",          # 特权模式提示符
            r"\]\s*$",         # 系统/接口视图提示符
        ]

    def login_device(
        self,
        device_ip: str,
        username: str,
        password: str,
        port: int = 23,
        login_timeout: int = 15,
    ) -> str:
        """
        在跳板机上 telnet 登录网络设备。

        返回登录后的欢迎/提示文本。
        """
        # 发送 telnet 命令（跳板机上执行 telnet ip 即可，不指定端口）
        self.ssh.send_command(f"telnet {device_ip}", add_newline=True)

        # 等待用户名或密码提示
        idx, output = self.ssh.expect(
            [
                r"[Uu]sername\s*:\s*"
            ],
            timeout=login_timeout,
        )

        if idx in (0, 1):  # Username / Login
            self.ssh.send_command(username)
            idx, output = self.ssh.expect(
                [r"[Pp]assword\s*:\s*", r">\s*$", r"#\s*$"],
                timeout=login_timeout,
            )

        if idx == 0:  # Password
            self.ssh.send_command(password)
            idx, output = self.ssh.expect(
                self.prompt_patterns,
                timeout=login_timeout,
            )

        # 登录成功后，尝试关闭分页（兼容华为/H3C/思科等）
        self._try_disable_paging()

        # 如果已经到达提示符，返回输出
        return output

    def _try_disable_paging(self):
        """尝试发送关闭分页命令，失败静默处理。"""
        paging_cmds = [
            "screen-length 0 temporary",
            "terminal length 0",
            "undo screen-length",
        ]
        for cmd in paging_cmds:
            try:
                self.ssh.send_command(cmd)
                # 短暂等待并读取输出，不校验结果
                time.sleep(0.3)
                self.ssh._read_available(timeout=0.5)
            except Exception:
                pass

    def send_command_wait(
        self,
        command: str,
        wait_patterns: Optional[List[str]] = None,
        timeout: int = 200,
    ) -> str:
        """发送命令并等待特定输出或默认提示符。"""
        self.ssh.send_command(command)
        patterns = wait_patterns or self.prompt_patterns
        _, output = self.ssh.expect(patterns, timeout=timeout)
        return output

    def send_command_simple(self, command: str, timeout: int = 200) -> str:
        """发送命令，等待任意提示符返回。"""
        return self.send_command_wait(command, timeout=timeout)
