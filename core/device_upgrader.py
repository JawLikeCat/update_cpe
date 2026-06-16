import time
from typing import List, Dict, Callable, Optional
from core.ssh_client import SSHClient, JumpHostTelnet


class UpgradeResult:
    def __init__(self, device_ip: str, success: bool, message: str):
        self.device_ip = device_ip
        self.success = success
        self.message = message
        self.download_success = None  # True/False/None (None表示未执行)
        self.reboot_success = None    # True/False/None (None表示未执行)
        self.command_results = []     # 命令执行结果列表 [(命令, 结果), ...]


def _format_commands(commands: List[str], variables: Dict[str, str]) -> List[str]:
    """对命令列表进行变量替换。"""
    formatted = []
    for cmd in commands:
        new_cmd = cmd
        for key, value in variables.items():
            new_cmd = new_cmd.replace(f"{{{key}}}", str(value))
        formatted.append(new_cmd)
    return formatted


class DeviceUpgrader:
    """网络设备版本升级器。"""

    # 写死的下载命令模板
    DOWNLOAD_CMD_TEMPLATE = "copy ftp aliftpraisecom aliftpraisecom 101.201.54.165 {version_name} image"

    def __init__(
        self,
        jump_host: str,
        jump_port: int,
        jump_user: str,
        jump_pass: str,
        commands: List[str],
        log_callback: Optional[Callable[[str], None]] = None,
        version_name: str = "",
        download_wait: int = 180,
    ):
        self.jump_host = jump_host
        self.jump_port = jump_port
        self.jump_user = jump_user
        self.jump_pass = jump_pass
        self.commands = commands
        self.log_callback = log_callback
        self.version_name = version_name
        self.download_wait = download_wait

    def _log(self, message: str):
        if self.log_callback:
            self.log_callback(message)

    def upgrade_device(self, device: Dict[str, str]) -> UpgradeResult:
        """
        对单台设备执行升级流程。

        流程:
        1. SSH 连接跳板机
        2. Telnet 登录设备
        3. 执行升级命令（支持变量替换）
        4. 断开连接
        """
        ip = device["ip"]
        username = device.get("username", "")
        password = device.get("password", "")

        ssh = SSHClient()
        try:
            self._log(f"[{ip}] 正在连接跳板机 {self.jump_host}...")
            ssh.connect(
                hostname=self.jump_host,
                port=self.jump_port,
                username=self.jump_user,
                password=self.jump_pass,
            )
            self._log(f"[{ip}] 跳板机连接成功")

            # 在跳板机上 telnet 登录设备
            telnet = JumpHostTelnet(ssh)
            self._log(f"[{ip}] 正在通过 Telnet 登录设备...")
            login_output = telnet.login_device(ip, username, password)
            self._log(f"[{ip}] 设备登录成功")

            # 如果升级命令为空，默认执行下载命令
            if self.commands:
                raw_cmds = self.commands
            else:
                # 默认执行下载命令（需要版本名称）
                if self.version_name:
                    download_cmd = self.DOWNLOAD_CMD_TEMPLATE.format(version_name=self.version_name)
                    raw_cmds = ["enable", download_cmd, "reboot"]
                else:
                    # 如果没有版本名称，只执行 show version 测试连通性
                    raw_cmds = ["show version"]

            # 变量替换
            variables = {
                "device_ip": ip,
                "jump_host": self.jump_host,
            }
            
            # 如果版本名称不为空，添加到变量中
            if self.version_name:
                variables["version_name"] = self.version_name
            
            cmds = _format_commands(raw_cmds, variables)

            # 创建结果对象
            result = UpgradeResult(ip, True, "升级成功完成")

            for idx, cmd in enumerate(cmds, 1):
                # 特殊指令: WAIT <秒数> 表示执行后等待若干秒
                stripped = cmd.strip()
                if stripped.upper().startswith("WAIT "):
                    try:
                        seconds = float(stripped[5:].strip())
                    except ValueError:
                        self._log(f"[{ip}] 无效的 WAIT 指令: {cmd}")
                        continue
                    self._log(f"[{ip}] 等待 {seconds} 秒...")
                    time.sleep(seconds)
                    self._log(f"[{ip}] 等待结束")
                    continue

                self._log(f"[{ip}] 执行命令 ({idx}/{len(cmds)}): {cmd}")
                
                # 如果是下载命令（包含 "copy ftp"），使用较长的超时时间
                if "copy ftp" in cmd.lower():
                    self._log(f"[{ip}] 检测到下载命令，设置超时时间为 {self.download_wait} 秒")
                    try:
                        output = telnet.send_command_simple(cmd, timeout=self.download_wait)
                        self._log(f"[{ip}] 命令输出:\n{output}")
                        
                        # 检查下载结果
                        if "failed" in output.lower():
                            result.download_success = False
                            result.command_results.append((cmd, "失败"))
                            ssh.disconnect()
                            self._log(f"[{ip}] 下载失败: {output}")
                            result.success = False
                            result.message = f"下载失败: {output}"
                            return result
                        elif "success" in output.lower():
                            result.download_success = True
                            result.command_results.append((cmd, "成功"))
                            self._log(f"[{ip}] Download image({self.version_name}) success!")
                        else:
                            result.download_success = False
                            result.command_results.append((cmd, "未知"))
                        time.sleep(0.5)
                    except Exception as e:
                        result.download_success = False
                        result.command_results.append((cmd, f"异常: {str(e)}"))
                        ssh.disconnect()
                        self._log(f"[{ip}] 下载异常: {e}")
                        result.success = False
                        result.message = f"下载异常: {e}"
                        return result
                    
                elif cmd.lower() == "reboot":
                    # 发送 reboot 命令
                    self._log(f"[{ip}] 发送 reboot 命令")
                    try:
                        telnet.ssh.send_command(cmd)
                        # 等待确认提示（只匹配 confirm 关键字，简化匹配）
                        _, output = telnet.ssh.expect(
                            [r"confirm", r"y/n"],
                            timeout=5
                        )
                        self._log(f"[{ip}] 收到重启确认提示:\n{output}")
                        # 立即发送 y 确认
                        self._log(f"[{ip}] 输入 y 确认重启")
                        telnet.ssh.send_command("y")
                        time.sleep(3)
                        # 读取重启输出
                        output = telnet.ssh._read_available(timeout=15)
                        self._log(f"[{ip}] 重启命令输出:\n{output}")
                        result.reboot_success = True
                        result.command_results.append((cmd, "成功"))
                    except TimeoutError:
                        self._log(f"[{ip}] 等待重启确认提示超时")
                        # 尝试直接发送 y
                        telnet.ssh.send_command("y")
                        time.sleep(2)
                        output = telnet.ssh._read_available(timeout=10)
                        self._log(f"[{ip}] 超时后发送 y 的输出:\n{output}")
                        result.reboot_success = True
                        result.command_results.append((cmd, "成功"))
                    except Exception as e:
                        self._log(f"[{ip}] 重启异常: {e}")
                        result.reboot_success = False
                        result.command_results.append((cmd, f"异常: {str(e)}"))
                    
                else:
                    try:
                        output = telnet.send_command_simple(cmd, timeout=60)
                        self._log(f"[{ip}] 命令输出:\n{output}")
                        # 记录命令和返回的字符串（截取前200字符避免过长）
                        result.command_results.append((cmd, output.strip()[:200]))
                        time.sleep(0.5)
                    except Exception as e:
                        self._log(f"[{ip}] 命令执行异常: {e}")
                        result.command_results.append((cmd, f"异常: {str(e)}"))

            ssh.disconnect()
            self._log(f"[{ip}] 升级流程完成")
            return result

        except Exception as e:
            ssh.disconnect()
            err_msg = str(e)
            self._log(f"[{ip}] 错误: {err_msg}")
            result = UpgradeResult(ip, False, err_msg)
            return result

    def upgrade_all(
        self,
        devices: List[Dict[str, str]],
        stop_on_error: bool = False,
        progress_callback=None,
    ) -> List[UpgradeResult]:
        """批量升级设备。"""
        results = []
        for idx, device in enumerate(devices):
            result = self.upgrade_device(device)
            results.append(result)
            if progress_callback:
                progress_callback(idx + 1)
            if stop_on_error and not result.success:
                self._log("遇到错误，停止后续设备升级")
                break
        return results
