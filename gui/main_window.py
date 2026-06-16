import os
import sys
from typing import List, Dict

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QHeaderView,
    QFileDialog,
    QMessageBox,
    QProgressBar,
    QSpinBox,
    QCheckBox,
    QAction,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from core.excel_reader import read_devices_from_excel
from core.device_upgrader import DeviceUpgrader, UpgradeResult


class UpgradeWorker(QThread):
    """在后台线程执行升级任务，避免阻塞 GUI。"""

    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(list)

    def __init__(
        self,
        jump_host: str,
        jump_port: int,
        jump_user: str,
        jump_pass: str,
        commands: List[str],
        devices: List[Dict[str, str]],
        version_name: str = "",
        download_wait: int = 180,
        var_a: str = "",
        var_b: str = "",
        var_c: str = "",
        var_d: str = "",
        var_a_inc: bool = False,
        var_b_inc: bool = False,
        var_c_inc: bool = False,
        var_d_inc: bool = False,
    ):
        super().__init__()
        self.jump_host = jump_host
        self.jump_port = jump_port
        self.jump_user = jump_user
        self.jump_pass = jump_pass
        self.commands = commands
        self.devices = devices
        self.version_name = version_name
        self.download_wait = download_wait
        self.var_a = var_a
        self.var_b = var_b
        self.var_c = var_c
        self.var_d = var_d
        self.var_a_inc = var_a_inc
        self.var_b_inc = var_b_inc
        self.var_c_inc = var_c_inc
        self.var_d_inc = var_d_inc

    def run(self):
        upgrader = DeviceUpgrader(
            jump_host=self.jump_host,
            jump_port=self.jump_port,
            jump_user=self.jump_user,
            jump_pass=self.jump_pass,
            commands=self.commands,
            version_name=self.version_name,
            download_wait=self.download_wait,
            log_callback=lambda msg: self.log_signal.emit(msg),
            var_a=self.var_a,
            var_b=self.var_b,
            var_c=self.var_c,
            var_d=self.var_d,
            var_a_inc=self.var_a_inc,
            var_b_inc=self.var_b_inc,
            var_c_inc=self.var_c_inc,
            var_d_inc=self.var_d_inc,
        )
        results = upgrader.upgrade_all(
            self.devices,
            progress_callback=lambda current: self.progress_signal.emit(current),
        )
        self.finished_signal.emit(results)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CPE升级版本配置")
        self.setMinimumSize(1000, 700)
        self.devices: List[Dict[str, str]] = []
        self.worker: UpgradeWorker = None
        self.upgrade_results = []  # 存储升级结果

        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 菜单栏
        menubar = self.menuBar()
        help_menu = menubar.addMenu("帮助")
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        # POP跳板机登录配置区域
        jump_group = QGroupBox("POP跳板机登录配置")
        jump_layout = QHBoxLayout()

        self.jump_ip_input = QLineEdit()
        self.jump_ip_input.setPlaceholderText("跳板机 IP 地址")
        self.jump_ip_input.setMinimumWidth(150)

        self.jump_port_spin = QSpinBox()
        self.jump_port_spin.setRange(1, 65535)
        self.jump_port_spin.setValue(10001)
        self.jump_port_spin.setMinimumWidth(80)

        self.jump_user_input = QLineEdit()
        self.jump_user_input.setPlaceholderText("用户名")

        self.jump_pass_input = QLineEdit()
        self.jump_pass_input.setPlaceholderText("密码")
        self.jump_pass_input.setEchoMode(QLineEdit.Password)

        jump_layout.addWidget(QLabel("IP:"))
        jump_layout.addWidget(self.jump_ip_input)
        jump_layout.addWidget(QLabel("端口:"))
        jump_layout.addWidget(self.jump_port_spin)
        jump_layout.addWidget(QLabel("用户名:"))
        jump_layout.addWidget(self.jump_user_input)
        jump_layout.addWidget(QLabel("密码:"))
        jump_layout.addWidget(self.jump_pass_input)
        jump_layout.addStretch()
        jump_group.setLayout(jump_layout)
        main_layout.addWidget(jump_group)

        # 版本配置区域
        version_group = QGroupBox("版本配置")
        version_layout = QHBoxLayout()

        self.version_name_input = QLineEdit()
        self.version_name_input.setPlaceholderText("版本文件名（如 MSG5200_SYSTEM_4.23.384_20250724.bin）")
        self.version_name_input.setMinimumWidth(300)

        self.download_wait_spin = QSpinBox()
        self.download_wait_spin.setRange(30, 600)
        self.download_wait_spin.setValue(180)
        self.download_wait_spin.setMinimumWidth(80)

        version_layout.addWidget(QLabel("版本名称:"))
        version_layout.addWidget(self.version_name_input)
        version_layout.addWidget(QLabel("升级版本下载所需时间（秒）:"))
        version_layout.addWidget(self.download_wait_spin)
        version_layout.addStretch()
        version_group.setLayout(version_layout)
        main_layout.addWidget(version_group)

        # 变量参数控制区域
        var_group = QGroupBox("变量参数控制")
        var_layout = QGridLayout()
        
        # 变量输入
        self.var_a_input = QLineEdit()
        self.var_a_input.setPlaceholderText("变量 a 的值")
        self.var_b_input = QLineEdit()
        self.var_b_input.setPlaceholderText("变量 b 的值")
        self.var_c_input = QLineEdit()
        self.var_c_input.setPlaceholderText("变量 c 的值")
        self.var_d_input = QLineEdit()
        self.var_d_input.setPlaceholderText("变量 d 的值")
        
        # 变量递增选项
        self.var_a_inc = QCheckBox("a 自增")
        self.var_b_inc = QCheckBox("b 自增")
        self.var_c_inc = QCheckBox("c 自增")
        self.var_d_inc = QCheckBox("d 自增")
        
        var_layout.addWidget(QLabel("变量 a:"), 0, 0)
        var_layout.addWidget(self.var_a_input, 0, 1)
        var_layout.addWidget(self.var_a_inc, 0, 2)
        var_layout.addWidget(QLabel("变量 b:"), 1, 0)
        var_layout.addWidget(self.var_b_input, 1, 1)
        var_layout.addWidget(self.var_b_inc, 1, 2)
        var_layout.addWidget(QLabel("变量 c:"), 2, 0)
        var_layout.addWidget(self.var_c_input, 2, 1)
        var_layout.addWidget(self.var_c_inc, 2, 2)
        var_layout.addWidget(QLabel("变量 d:"), 3, 0)
        var_layout.addWidget(self.var_d_input, 3, 1)
        var_layout.addWidget(self.var_d_inc, 3, 2)
        
        var_group.setLayout(var_layout)
        main_layout.addWidget(var_group)

        # CPE命令执行输入区域
        cmd_group = QGroupBox("CPE命令执行输入")
        cmd_layout = QVBoxLayout()
        self.cmd_text = QTextEdit()
        self.cmd_text.setPlaceholderText(
            "【版本升级流程示例，默认执行升级，若只需要升级则不需要在此处输入升级相关命令，若升级前需要执行某些命令则需要在此处输入需要执行的命令以及升级相关命令】\n"
            "enable\n"
            "copy ftp aliftpraisecom aliftpraisecom 101.201.54.165 {version_name} image\n"
            "reboot\n\n"
            "【说明】\n"
            "可用变量: {device_ip}, {jump_host}, {version_name}, {a}, {b}, {c}, {d}\n"
            "{version_name} 会被界面上的版本名称替换\n"
            "{a}, {b}, {c}, {d} 会被上方变量参数替换，勾选自增选项后每执行完一个设备，对应变量自动加1\n"
            "copy ftp 命令会自动使用界面上设置的下载等待时间\n"
            "如果留空且设置了版本名称，默认执行下载命令 + reboot（自动确认）\n"
            "特殊指令: WAIT <秒数>  例如 WAIT 180 表示执行后等待 3 分钟"
        )
        self.cmd_text.setMaximumHeight(180)
        cmd_layout.addWidget(self.cmd_text)
        cmd_group.setLayout(cmd_layout)
        main_layout.addWidget(cmd_group)

        # CPE设备列表区域
        device_group = QGroupBox("CPE设备列表（通过 Excel 导入）")
        device_layout = QVBoxLayout()

        btn_layout = QHBoxLayout()
        self.import_btn = QPushButton("导入 Excel")
        self.import_btn.setToolTip("导入包含 CPE 设备 IP、用户名、密码的 Excel 文件")
        self.clear_btn = QPushButton("清空列表")
        self.device_count_label = QLabel("设备数量: 0")
        btn_layout.addWidget(self.import_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.device_count_label)

        self.device_table = QTableWidget()
        self.device_table.setColumnCount(4)
        self.device_table.setHorizontalHeaderLabels(["序号", "CPE IP 地址", "用户名", "密码"])
        self.device_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.device_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.device_table.setEditTriggers(QTableWidget.NoEditTriggers)

        device_layout.addLayout(btn_layout)
        device_layout.addWidget(self.device_table)
        device_group.setLayout(device_layout)
        main_layout.addWidget(device_group, stretch=1)

        # 操作区域
        action_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始升级")
        self.start_btn.setStyleSheet("QPushButton { font-weight: bold; font-size: 14px; padding: 8px 20px; }")
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.export_btn = QPushButton("导出结果")
        self.export_btn.setEnabled(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        action_layout.addWidget(self.start_btn)
        action_layout.addWidget(self.stop_btn)
        action_layout.addWidget(self.export_btn)
        action_layout.addWidget(self.progress_bar, stretch=1)
        main_layout.addLayout(action_layout)

        # 日志区域
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.WidgetWidth)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group, stretch=1)

    def _connect_signals(self):
        self.import_btn.clicked.connect(self._import_excel)
        self.clear_btn.clicked.connect(self._clear_devices)
        self.start_btn.clicked.connect(self._start_upgrade)
        self.stop_btn.clicked.connect(self._stop_upgrade)
        self.export_btn.clicked.connect(self._export_results)

    def _show_about(self):
        QMessageBox.about(
            self,
            "关于",
            "<b>网络设备版本升级工具</b><br><br>"
            "功能：通过 SSH 登录跳板机，再 Telnet 登录网络设备执行版本升级。<br>"
            "支持 Excel 批量导入、命令变量替换。<br>",
        )

    def _import_excel(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择 Excel 文件", "", "Excel Files (*.xlsx *.xls)"
        )
        if not filepath:
            return
        try:
            self.devices = read_devices_from_excel(filepath)
            self._refresh_table()
            self._log(f"成功导入 {len(self.devices)} 台设备: {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))
            self._log(f"导入失败: {e}")

    def _refresh_table(self):
        self.device_table.setRowCount(len(self.devices))
        for i, dev in enumerate(self.devices):
            self.device_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.device_table.setItem(i, 1, QTableWidgetItem(dev["ip"]))
            self.device_table.setItem(i, 2, QTableWidgetItem(dev["username"]))
            self.device_table.setItem(i, 3, QTableWidgetItem(dev["password"]))
        self.device_count_label.setText(f"设备数量: {len(self.devices)}")

    def _clear_devices(self):
        self.devices.clear()
        self._refresh_table()
        self._log("已清空设备列表")

    def _log(self, message: str):
        self.log_text.append(message)

    def _get_commands(self) -> List[str]:
        raw = self.cmd_text.toPlainText().strip()
        if not raw:
            return []
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def _validate_inputs(self) -> bool:
        if not self.jump_ip_input.text().strip():
            QMessageBox.warning(self, "输入错误", "请输入跳板机 IP 地址")
            return False
        if not self.jump_user_input.text().strip():
            QMessageBox.warning(self, "输入错误", "请输入跳板机用户名")
            return False
        if not self.jump_pass_input.text().strip():
            QMessageBox.warning(self, "输入错误", "请输入跳板机密码")
            return False
        if not self.devices:
            QMessageBox.warning(self, "输入错误", "请先导入网络设备列表")
            return False
        return True

    def _start_upgrade(self):
        if not self._validate_inputs():
            return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setRange(0, len(self.devices))
        self.progress_bar.setValue(0)
        self.log_text.clear()

        self.worker = UpgradeWorker(
            jump_host=self.jump_ip_input.text().strip(),
            jump_port=self.jump_port_spin.value(),
            jump_user=self.jump_user_input.text().strip(),
            jump_pass=self.jump_pass_input.text().strip(),
            commands=self._get_commands(),
            devices=self.devices,
            version_name=self.version_name_input.text().strip(),
            download_wait=self.download_wait_spin.value(),
            var_a=self.var_a_input.text().strip(),
            var_b=self.var_b_input.text().strip(),
            var_c=self.var_c_input.text().strip(),
            var_d=self.var_d_input.text().strip(),
            var_a_inc=self.var_a_inc.isChecked(),
            var_b_inc=self.var_b_inc.isChecked(),
            var_c_inc=self.var_c_inc.isChecked(),
            var_d_inc=self.var_d_inc.isChecked(),
        )
        self.worker.log_signal.connect(self._log)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.finished_signal.connect(self._on_upgrade_finished)
        self.worker.start()

        self._log("========== 升级开始 ==========")

    def _stop_upgrade(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait(2000)
            self._log("========== 升级已终止 ==========")
        self._reset_ui_state()

    def _on_upgrade_finished(self, results: List[UpgradeResult]):
        # 保存升级结果
        self.upgrade_results = results
        
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count
        self._log(
            f"\n========== 升级结束 ==========\n"
            f"成功: {success_count} 台, 失败: {fail_count} 台"
        )
        self._reset_ui_state()
        # 启用导出按钮
        self.export_btn.setEnabled(True)
        QMessageBox.information(
            self, "完成", f"升级完成！\n成功: {success_count} 台\n失败: {fail_count} 台\n\n可点击'导出结果'按钮导出详细报告"
        )

    def _reset_ui_state(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setValue(self.progress_bar.maximum())

    def _export_results(self):
        if not self.upgrade_results:
            QMessageBox.warning(self, "提示", "没有可导出的升级结果")
            return
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存升级结果", "", "Excel Files (*.xlsx)"
        )
        if not filepath:
            return
        
        try:
            import pandas as pd
            
            # 构建表格数据
            data = []
            for result in self.upgrade_results:
                row = {
                    "设备IP": result.device_ip,
                    "版本下载情况": self._get_download_status(result),
                    "reboot": self._get_reboot_status(result),
                }
                # 添加命令执行结果
                for i, (cmd, cmd_result) in enumerate(result.command_results, 1):
                    row[f"执行命令{i}"] = f"{cmd} -> {cmd_result}"
                data.append(row)
            
            # 创建 DataFrame
            df = pd.DataFrame(data)
            
            # 保存到 Excel
            df.to_excel(filepath, index=False)
            
            QMessageBox.information(self, "成功", f"升级结果已导出到:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出失败: {str(e)}")
    
    def _get_download_status(self, result):
        if result.download_success is True:
            return "成功"
        elif result.download_success is False:
            return "失败"
        else:
            return "未执行"
    
    def _get_reboot_status(self, result):
        if result.reboot_success is True:
            return "成功"
        elif result.reboot_success is False:
            return "失败"
        else:
            return "未执行"
