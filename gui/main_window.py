# -*- coding: utf-8 -*-

# 导入所需的Python标准库模块
import sys
import os
import time
import json
import platform
import subprocess
import psutil
import gc
import logging
import traceback

# 获取当前文件的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录
project_root = os.path.dirname(current_dir)
# 将项目根目录添加到Python路径
sys.path.insert(0, project_root)

# 导入PyQt5相关模块
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import (QMainWindow, QPushButton, QLabel, QFileDialog, 
                             QLineEdit, QVBoxLayout, QHBoxLayout, QWidget, 
                             QProgressBar, QTextEdit, QSizePolicy, QDesktopWidget, 
                             QGroupBox, QCheckBox, QGridLayout, QFrame)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPainter, QColor, QPalette, QBrush, QIcon

# 导入OpenCV库
import cv2

# 导入自定义模块
from processors.video_analyzer import VideoAnalyzer
from processors.video_processor import VideoProcessor
from utils.file_utils import get_output_path, get_file_size, is_valid_video_file

# 自定义理类，用于去除按钮焦点边框
class AppleStyleDelegate(QtWidgets.QStyledItemDelegate):
    def paint(self, painter, option, index):
        # 如果父对象是QPushButton，则移除焦点状态
        if isinstance(self.parent(), QPushButton):
            option.state &= ~QtWidgets.QStyle.State_HasFocus
        # 调用父类的paint方法
        super().paint(painter, option, index)

# 帧删除图表类，用于可视化删除的帧
class FrameDeletionChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.deletion_data = []  # 初始化删除数据列表

    def update_data(self, data):
        # 更新删除数据
        self.deletion_data = data
        self.update()  # 触发重绘

    def paintEvent(self, event):
        # 绘制事件处理
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  # 设置抗锯齿

        if not self.deletion_data:
            return  # 如果没有数据，直接返回

        width = self.width()
        height = self.height()
        # 找出最大帧数
        max_frames = max(self.deletion_data, key=lambda x: x[1])[1]

        # 绘制每个删除的帧
        for sec, frame in self.deletion_data:
            x = int(sec / self.deletion_data[-1][0] * width)
            y = int((1 - frame / max_frames) * height)
            painter.setPen(QColor(255, 0, 0))  # 设置红色画笔
            painter.drawPoint(x, y)  # 绘制点

# 性能监控线程类
class PerformanceMonitor(QThread):
    update_signal = pyqtSignal(float, float)  # 定义信号，用于更新UI

    def __init__(self):
        super().__init__()
        self.is_running = True  # 控制线程运行的标志

    def run(self):
        while self.is_running:
            # 获取CPU和内存使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            # 发送信号更新UI
            self.update_signal.emit(cpu_percent, memory_percent)

    def stop(self):
        # 停止线程
        self.is_running = False

# 自定义进度条类
class CustomProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)  # 隐藏默认文本
        # 设置样式
        self.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #E5E5EA;
                height: 8px;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #007AFF;
                border-radius: 4px;
            }
        """)

    def paintEvent(self, event):
        # 自定绘件
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制文本
        painter.setPen(Qt.black)
        painter.setFont(QFont("SF Pro Text", 10, QFont.Bold))
        painter.drawText(self.rect(), Qt.AlignCenter, f"{max(0, self.value())}%")
        
        # 如果进度为0，绘制一个小的蓝点
        if self.value() <= 0:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#007AFF")))
            painter.drawEllipse(self.rect().left() + 5, self.rect().center().y() - 5, 10, 10)

# 主窗口类
class VideoProcessorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.temp_files = []  # 初始化 temp_files 属性
        self.video_info = {}  # 初始化 video_info 字典
        self.setup_ui_components()
        self.setup_connections()
        self.load_settings()
        self.initialize_performance_monitor()

    def setup_ui_components(self):
        self.setFont(QFont("SF Pro Text", 12))  # 设置默认字体
        
        # 设置应用图标
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app_icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.video_info = None  # 存储视频信息
        self.start_time = None  # 处理开始时间
        self.timer = QTimer(self)  # 创建定时器
        self.deleted_frames_count = 0  # 删除帧计数
        self.current_second = 0  # 前理的秒数
        self.analysis_start_time = None  # 分析开始时间
        
        self.settings_file = 'settings.json'  # 设置文件名
        
        # 检测操作系统
        self.is_windows = platform.system() == "Windows"
        
        self.initial_memory_usage = self.get_memory_usage()  # 获取初始内存使用量
        self.memory_label = QLabel(f'内存占用: {self.initial_memory_usage:.2f} MB', self)  # 创建内存标签
        
        self.setWindowTitle('RandFrameDel')  # 修改这行
        
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        # 调整窗口大小
        if self.is_windows:
            self.setFixedSize(380, 780)  # 稍微减小窗口宽度，保持高度
        else:
            self.setFixedSize(360, 700)  # Mac系统保持不变

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        
        # 调整布局间距
        if self.is_windows:
            layout.setSpacing(8)  # 为Windows系统置较小的布局间距
            layout.setContentsMargins(15, 15, 15, 15)  # 为Windows系统设置较小的边距
        else:
            layout.setSpacing(15)  # 为Mac系统设置较大的布局间距
            layout.setContentsMargins(15, 15, 15, 15)  # 为Mac系统设置较大的边距

        # 根据操作系统调整字体
        if self.is_windows:
            font = QFont("Microsoft YaHei", 8)  # Windows系统使用微软雅黑字体，主字体大小为10
            small_font = QFont("Microsoft YaHei", 8)  # Windows系统处理信息标题字体大小为10
            info_font = QFont("Microsoft YaHei", 12)  # Windows系统信息框内字体大小为12
            author_font = QFont("Microsoft YaHei", 7)  # Windows系统作者信息字体大小为9
        else:
            font = QFont("SF Pro Text", 12)  # Mac系统使用SF Pro Text字体，主字体大小为12
            small_font = QFont("SF Pro Text", 11)  # Mac系统处理信息标题字体大小为11
            info_font = QFont("SF Pro Text", 11)  # Mac系统信息框内字体大小为11
            author_font = QFont("SF Pro Text", 10)  # Mac小为10

        # 钮体
        button_font = QFont("Microsoft YaHei" if self.is_windows else "SF Pro Text", 11)  # 根据操作系统选择按钮字体，大小为11

        # 创建文件选择区域布局
        file_layout = QVBoxLayout()
        self.load_button = QPushButton('加载视频', self)
        self.load_button.setFont(button_font)  # 设置加载按钮字体
        button_height = 45 if self.is_windows else 40  # 根据操作系统设置按钮高度
        self.load_button.setMinimumHeight(button_height)
        file_layout.addWidget(self.load_button)
        self.path_label = QLabel('', self)
        self.path_label.setFont(font)
        self.path_label.setWordWrap(True)  # 允许文本换行
        self.path_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)  # 设置文本左对齐和顶部对齐
        file_layout.addWidget(self.path_label)
        layout.addLayout(file_layout)

        # 创建进度条布局
        progress_layout = QVBoxLayout()
        self.progress_bar = CustomProgressBar(self)
        self.progress_bar.setValue(0)
        progress_bar_height = 25 if self.is_windows else 20  # 根据操作系统设置进度条高度
        self.progress_bar.setFixedHeight(progress_bar_height)
        progress_layout.addWidget(self.progress_bar)
        layout.addLayout(progress_layout)

        # 创建参数输入区域
        params_group = QGroupBox("处理参数")
        params_group.setFont(font)
        params_layout = QGridLayout()
        self.interval_label = QLabel('间隔秒数:', self)
        self.interval_label.setFont(font)
        self.interval_input = QLineEdit(self)
        self.interval_input.setFont(font)
        self.delete_label = QLabel('删除帧数:', self)
        self.delete_label.setFont(font)
        self.delete_input = QLineEdit(self)
        self.delete_input.setFont(font)
        params_layout.addWidget(self.interval_label, 0, 0)
        params_layout.addWidget(self.interval_input, 0, 1)
        params_layout.addWidget(self.delete_label, 1, 0)
        params_layout.addWidget(self.delete_input, 1, 1)
        params_group.setLayout(params_layout)
        layout.addWidget(params_group)

        # 创建控制按钮和实时统计信息布局
        control_stats_layout = QHBoxLayout()
        
        control_layout = QVBoxLayout()
        self.process_button = QPushButton('开始处理', self)
        self.process_button.setFont(button_font)  # 设置处理按钮字体
        self.process_button.setMinimumHeight(button_height)
        self.process_button.setEnabled(False)
        
        self.cancel_button = QPushButton('取消处理', self)
        self.cancel_button.setFont(button_font)  # 设置取消按钮字体
        self.cancel_button.setMinimumHeight(button_height)
        self.cancel_button.setEnabled(False)
        control_layout.addWidget(self.process_button)
        control_layout.addWidget(self.cancel_button)
        
        stats_layout = QVBoxLayout()
        self.time_label = QLabel('预计剩余: --:--', self)
        self.time_label.setFont(font)
        self.frames_deleted_label = QLabel('累计删除总帧数: 0', self)
        self.frames_deleted_label.setFont(font)
        self.performance_label = QLabel('CPU: --%, 内存: --%', self)
        self.performance_label.setFont(font)
        stats_layout.addWidget(self.time_label)
        stats_layout.addWidget(self.frames_deleted_label)
        stats_layout.addWidget(self.performance_label)
        stats_layout.addWidget(self.memory_label)
        
        control_stats_layout.addLayout(control_layout)
        control_stats_layout.addLayout(stats_layout)
        layout.addLayout(control_stats_layout)

        # 创建详细信息文本框
        info_group = QGroupBox("Processing Information")  # 设置信息组标题
        info_group.setFont(QFont("Microsoft YaHei" if self.is_windows else "SF Pro Text", 8))  # 设置信息组标题字体
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(5, 5, 5, 5)
        self.info_text = QTextEdit(self)
        self.info_text.setFont(QFont("Microsoft YaHei" if self.is_windows else "SF Pro Text", 8))  # 设置信息文本字体
        self.info_text.setReadOnly(True)
        info_text_height = 280 if self.is_windows else 220  # 根据操作系统设置信息文本框高度
        self.info_text.setMinimumHeight(info_text_height)
        info_layout.addWidget(self.info_text)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group, 1)

        # 创建选项和作者息布局
        options_author_layout = QHBoxLayout()
        options_author_layout.setContentsMargins(0, 5, 0, 0)  # 设置布局边距

        left_layout = QHBoxLayout()
        self.auto_open_checkbox = QCheckBox("Open output folder", self)
        self.auto_open_checkbox.setFont(small_font)
        left_layout.addWidget(self.auto_open_checkbox)
        left_layout.addStretch(1)

        right_layout = QHBoxLayout()
        author_info = QLabel("z7  Email: ssinz1210@icloud.com", self)  # 设置作者信息
        author_info.setFont(author_font)
        author_info.setStyleSheet("color: #666666;")
        right_layout.addWidget(author_info)

        options_author_layout.addLayout(left_layout, 1)
        options_author_layout.addLayout(right_layout, 1)

        layout.addLayout(options_author_layout)

        central_widget.setLayout(layout)

        self.setStyleSheet(self.get_stylesheet())

        self.process_finished_called = False  # 添加这行来跟踪 process_finished 是否被调用

    def setup_connections(self):
        self.load_button.clicked.connect(self.load_video)
        self.process_button.clicked.connect(self.process_video)
        self.cancel_button.clicked.connect(self.cancel_processing)
        self.timer.timeout.connect(self.update_estimated_time)

    def initialize_performance_monitor(self):
        self.performance_monitor = PerformanceMonitor()
        self.performance_monitor.update_signal.connect(self.update_performance_info)
        self.performance_monitor.start()

    def get_stylesheet(self):
        return """
            QMainWindow {
                background-color: #ffffff;
            }
            QPushButton {
                background-color: #000000;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-size: 11px;
                font-family: "Microsoft YaHei";
            }
            QPushButton:hover {
                background-color: #333333;
            }
            QPushButton:pressed {
                background-color: #666666;
            }
            QLineEdit, QTextEdit {
                border: 1px solid #d1d1d6;
                border-radius: 4px;
                padding: 4px;
                background-color: #ffffff;
                font-size: 10px;
                font-family: "Microsoft YaHei";
            }
            QGroupBox {
                border: 1px solid #d1d1d6;
                border-radius: 3px;
                margin-top: 6px;
                background-color: #f2f2f7;
                font-size: 10px;
                font-family: "Microsoft YaHei";
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 7px;
                padding: 0 3px 0 3px;
            }
            QLabel, QCheckBox {
                color: #000000;
                font-size: 11px;
                font-family: "Microsoft YaHei";
            }
            QTextEdit {
                font-size: 10px;
            }
        """

    def center(self):
        # 获取屏幕几何信息
        screen = QDesktopWidget().screenNumber(QDesktopWidget().cursor().pos())
        center_point = QDesktopWidget().screenGeometry(screen).center()
        
        # 将窗口移动到屏幕中央
        frame_geometry = self.frameGeometry()
        frame_geometry.moveCenter(center_point)
        self.move(frame_geometry.topLeft())

    def load_video(self):
        file_path = self.get_video_file_path()
        if file_path:
            if self.is_valid_video_file(file_path):
                self.start_video_analysis(file_path)
            else:
                self.show_warning("请选择有效的视频文件")
        # 如果 file_path 为空（用户取消选择），不做任操作

    def get_video_file_path(self):
        return QFileDialog.getOpenFileName(self, "选择视频文件", os.path.expanduser("~"), "Video Files (*.mp4 *.avi *.mov)")[0]

    def is_valid_video_file(self, file_path):
        return is_valid_video_file(file_path)

    def start_video_analysis(self, file_path):
        self.analyzer = VideoAnalyzer(file_path)
        self.connect_analyzer_signals()
        self.analyzer.start()

    def connect_analyzer_signals(self):
        self.analyzer.progress.connect(self.update_progress)
        self.analyzer.finished.connect(self.on_analysis_finished)
        self.analyzer.error.connect(self.show_error_message)

    def update_progress(self, value, stage):
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(f"{stage}: {value}%")
        # 确保 GUI 更新
        QtWidgets.QApplication.processEvents()
        
        # 更新估计剩余时间
        if self.start_time is not None:
            elapsed_time = time.time() - self.start_time
            if value > 0:
                estimated_total_time = elapsed_time * 100 / value
                remaining_time = estimated_total_time - elapsed_time
                minutes, seconds = divmod(int(remaining_time), 60)
                self.time_label.setText(f'预计剩余: {minutes}分{seconds}秒')

    def display_video_info(self, info):
        self.video_info = info
        self.load_button.setEnabled(True)
        self.analysis_start_time = None
        self.timer.stop()
        self.time_label.setText('分析完成')
        
        info_text = "视频信息：\n"
        info_text += f"文件路径：{info['文件路径']}\n"
        info_text += f"文件名称：{info['文件名称']}\n"
        info_text += f"文件大小：{int(float(info['文件大小']))} MB\n"
        info_text += f"视频总帧数：{info['视频总帧数']}\n"
        info_text += f"帧率：{info['帧率']:.2f}\n"
        info_text += f"分辨率：{info['分辨率']}\n"
        info_text += f"时长：{info['时长']:.2f} 秒\n"
        info_text += f"是否包含音频：{'是' if info['是否包含音频'] else '否'}\n"
        if info['是否包含音频']:
            info_text += f"音频时长：{info['音频时长']:.2f} 秒\n"
            info_text += f"音频采样率：{info['音频采样率']} Hz\n"
        info_text += f"分析用时：{info['分析用时']:.2f} 秒\n"
        
        self.info_text.setText(info_text)
        self.process_button.setEnabled(True)

    def process_video(self):
        logging.info("开始处理视频")
        if not self.video_info:
            self.show_warning("请先加载视频")
            return
        if not os.path.exists(self.video_info['文件路径']):
            self.show_error_message(f"视频文件不存在: {self.video_info['文件路径']}")
            return
        try:
            interval_range = self.interval_input.text()
            delete_frames = int(self.delete_input.text())
            
            if not interval_range or delete_frames <= 0 or delete_frames > 30:
                self.show_warning("请输入有效的间隔范围和删除帧数（1-30）")
                return
            
            input_path = self.video_info['文件路径']
            output_path = get_output_path(input_path)
            
            self.processor = VideoProcessor(
                input_path, 
                output_path, 
                interval_range, 
                delete_frames,
                self.video_info['帧率'],
                {
                    'has_audio': self.video_info['是否包含音频'],
                    'audio_duration': self.video_info.get('音频时长'),
                    'audio_fps': self.video_info.get('音频采样率')
                },
                self.video_info['视频总帧数'],
                self.video_info
            )
            
            self.processor.progress.connect(self.update_progress)
            self.processor.finished.connect(self.process_finished)
            self.processor.frame_deleted_signal.connect(self.update_deleted_frames_info)
            self.processor.info_signal.connect(self.update_info_text)
            
            self.start_time = time.time()
            self.progress_bar.setValue(0)
            self.process_button.setEnabled(False)
            self.load_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.timer.start(1000)
            self.processing_start_time = time.time()
            self.deleted_frames_count = 0
            self.frames_deleted_label.setText('预计删除总帧数: 0')
            
            self.processor.start()
            logging.info("视频处理器已启动")
        except Exception as e:
            logging.error(f"处理视频时出错: {str(e)}", exc_info=True)
            self.show_error_message(f"处理视频时出错: {str(e)}")

    def update_deleted_frames_info(self, sec, frames):
        frames_per_second = int(self.video_info['帧率'])  # 修改这里
        start_frame = sec * frames_per_second
        end_frame = start_frame + frames_per_second - 1
        frame_info = [f"{frame - start_frame}/{frames_per_second - 1}" for frame in frames]
        frame_numbers = [f"{frame}/{self.video_info['视频总帧数']}" for frame in frames]  # 修改这里
        delete_info = f"视频第{sec}秒 (帧{start_frame}-{end_frame}): 删除第{', '.join(frame_info)}帧 (总帧数: {', '.join(frame_numbers)})"
        self.info_text.append(delete_info)
        self.deleted_frames_count += len(frames)
        self.frames_deleted_label.setText(f'预计删除总帧数: {self.deleted_frames_count}')
        self.info_text.verticalScrollBar().setValue(self.info_text.verticalScrollBar().maximum())

    def process_finished(self, result, deleted_frames, final_video_info):
        logging.info("处理完成回调被调用")
        if self.process_finished_called:
            return
        self.process_finished_called = True

        self.process_button.setEnabled(True)
        self.load_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.timer.stop()
        self.time_label.setText('处理完成')

        processing_end_time = time.time()
        total_processing_time = processing_end_time - self.processing_start_time
        
        verification_text = f"\n处理结果：\n"
        if 'error' in final_video_info:
            verification_text += f"处理出错：{final_video_info['error']}\n"
        else:
            verification_text += f"合成视频路径：{final_video_info.get('path', '未知')}\n"
            verification_text += f"总帧数：{final_video_info.get('frame_count', '未知')}\n"
            verification_text += f"视频大小：{final_video_info.get('size', '未知')} MB\n"
            
            # 修改这里，确保 'duration' 是数字类型
            duration = final_video_info.get('duration', '未知')
            if isinstance(duration, (int, float)):
                verification_text += f"视频时长：{duration:.2f} 秒\n"
            else:
                verification_text += f"视频时长：{duration}\n"
            
            fps = final_video_info.get('fps', '未知')
            if isinstance(fps, (int, float)):
                verification_text += f"帧率：{fps:.2f} fps\n"
            else:
                verification_text += f"帧率：{fps} fps\n"
            resolution = final_video_info.get('resolution', ('未知', '未知'))
            verification_text += f"分辨率：{resolution[0]}x{resolution[1]}\n"
            verification_text += f"是否包含音频：{'是' if final_video_info.get('has_audio', False) else '否'}\n"
            if final_video_info.get('has_audio', False):
                verification_text += f"音频采样率：{final_video_info.get('audio_fps', '未知')} Hz\n"
                audio_duration = final_video_info.get('audio_duration', '未知')
                if isinstance(audio_duration, (int, float)):
                    verification_text += f"音频时长：{audio_duration:.2f} 秒\n"
                else:
                    verification_text += f"音频时长：{audio_duration}\n"

        verification_text += f"总共删除的帧数：{self.deleted_frames_count}\n"
        verification_text += f"总处理时间：{total_processing_time:.2f} 秒\n"

        self.info_text.append(verification_text)
        self.info_text.verticalScrollBar().setValue(self.info_text.verticalScrollBar().maximum())

        if self.auto_open_checkbox.isChecked() and 'path' in final_video_info:
            output_dir = os.path.dirname(final_video_info['path'])
            self.open_file(output_dir)

    def open_file(self, path):
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":  # macOS
            subprocess.call(["open", path])
        else:  # Linux
            subprocess.call(["xdg-open", path])

    def update_estimated_time(self):
        if self.analysis_start_time is not None:
            elapsed_time = time.time() - self.analysis_start_time
            progress = self.progress_bar.value()
            if progress > 0:
                estimated_total_time = elapsed_time * 100 / progress
                remaining_time = estimated_total_time - elapsed_time
                minutes, seconds = divmod(int(remaining_time), 60)
                self.time_label.setText(f'预计剩余: {minutes}分{seconds}秒')
        elif self.start_time is not None:
            elapsed_time = time.time() - self.start_time
            progress = self.progress_bar.value()
            if progress > 0:
                estimated_total_time = elapsed_time * 100 / progress
                remaining_time = estimated_total_time - elapsed_time
                minutes, seconds = divmod(int(remaining_time), 60)
                self.time_label.setText(f'预计剩余: {minutes}分{seconds}秒')

    def cancel_processing(self):
        if hasattr(self, 'processor') and self.processor.isRunning():
            self.processor.stop()
            self.processor.wait()
            self.process_button.setEnabled(True)
            self.load_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.info_text.append("处理已取消。")
            self.timer.stop()
            self.time_label.setText('处理已取消')

    def get_output_frame_count(self, output_path):
        cap = cv2.VideoCapture(output_path)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        return frame_count

    def update_performance_info(self, cpu_percent, memory_percent):
        if hasattr(self, 'performance_label'):
            self.performance_label.setText(f'CPU: {cpu_percent:.1f}%, 内存: {memory_percent:.1f}%')
            self.update_memory_info()  # 更新内存使用信息
            self.performance_label.repaint()

    def closeEvent(self, event):
        try:
            # 停止所有正在运行的进程
            if hasattr(self, 'processor') and self.processor.isRunning():
                self.processor.stop()
                self.processor.wait()

            if hasattr(self, 'analyzer') and self.analyzer.isRunning():
                self.analyzer.stop()
                self.analyzer.wait()

            # 停止性能监控
            if hasattr(self, 'performance_monitor'):
                self.performance_monitor.stop()
                self.performance_monitor.wait()

            # 保存设置
            self.save_settings()

            # 清理临时文件
            self.cleanup_temp_files()

            # 释放视频和音频对象
            if hasattr(self, 'video_clip'):
                self.video_clip.close()
            if hasattr(self, 'audio_clip'):
                self.audio_clip.close()

            # 强制垃圾回收
            gc.collect()

        except Exception:
            pass

        super().closeEvent(event)

    def cleanup_temp_files(self):
        if hasattr(self, 'video_info') and self.video_info:
            input_path = self.video_info.get('文件路径', '')
            if input_path:
                output_path = get_output_path(input_path)
                temp_files = [
                    output_path.rsplit('.', 1)[0] + '_temp_video.mp4',
                    output_path.rsplit('.', 1)[0] + '_temp_audio.wav',
                    output_path.rsplit('.', 1)[0] + '_temp_processed_audio.wav'
                ]
                for file in temp_files:
                    if os.path.exists(file):
                        try:
                            os.remove(file)
                        except Exception:
                            pass

    def load_settings(self):
        try:
            with open(self.settings_file, 'r') as f:
                settings = json.load(f)
                self.interval_input.setText(settings.get('interval', ''))
                self.delete_input.setText(settings.get('delete_frames', ''))
                self.auto_open_checkbox.setChecked(settings.get('auto_open', False))
        except FileNotFoundError:
            # 如果文件不存在，就使用默认值
            pass
        except Exception:
            pass

    def save_settings(self):
        settings = {
            'interval': self.interval_input.text(),
            'delete_frames': self.delete_input.text(),
            'auto_open': self.auto_open_checkbox.isChecked()
        }
        with open(self.settings_file, 'w') as f:
            json.dump(settings, f)

    def get_memory_usage(self):
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024  # 转换为MB

    def update_memory_info(self):
        current_memory = self.get_memory_usage()
        self.memory_label.setText(f'内存占用: {current_memory:.2f} MB')

    def update_info_text(self, info):
        self.info_text.append(info)
        self.info_text.verticalScrollBar().setValue(self.info_text.verticalScrollBar().maximum())

    def show_warning(self, message):
        QtWidgets.QMessageBox.warning(self, "警告", message)

    def show_error_message(self, error_message):
        QtWidgets.QMessageBox.critical(self, "错误", error_message)

    def on_analysis_finished(self, result):
        self.display_video_info(result)