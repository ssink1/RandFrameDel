from PyQt5.QtCore import QThread, pyqtSignal
import cv2
import logging
import time
import os
from moviepy.editor import AudioFileClip
import subprocess
import json

class VideoAnalyzer(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, video_path):
        super().__init__()
        self.video_path = video_path
        self.logger = logging.getLogger(__name__)

    def run(self):
        try:
            self.logger.info(f"开始分析视频: {self.video_path}")
            start_time = time.time()
            
            self.progress.emit(0, "开始视频分析")

            # 获取文件信息
            file_size = os.path.getsize(self.video_path) / (1024 * 1024)  # 转换为MB
            file_name = os.path.basename(self.video_path)

            # 视频分析
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                raise IOError(f"无法打开视频文件: {self.video_path}")

            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = frame_count / fps if fps > 0 else 0

            cap.release()

            self.progress.emit(50, "视频分析完成")

            # 音频分析
            self.progress.emit(75, "开始音频分析")
            with AudioFileClip(self.video_path) as audio:
                has_audio = audio is not None
                audio_duration = audio.duration if has_audio else 0
                audio_fps = audio.fps if has_audio else 0

            # 获取视频比特率信息
            ffprobe_cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                self.video_path
            ]
            ffprobe_output = subprocess.check_output(ffprobe_cmd).decode('utf-8')
            ffprobe_data = json.loads(ffprobe_output)

            total_bitrate = ffprobe_data['format'].get('bit_rate')
            if total_bitrate:
                total_bitrate = f"{int(total_bitrate) // 1000}k"

            audio_bitrate = None
            for stream in ffprobe_data['streams']:
                if stream['codec_type'] == 'audio':
                    audio_bitrate = stream.get('bit_rate')
                    if audio_bitrate:
                        audio_bitrate = f"{int(audio_bitrate) // 1000}k"
                    break

            end_time = time.time()
            analysis_duration = end_time - start_time

            self.progress.emit(100, "分析完成")

            result = {
                "文件路径": os.path.abspath(self.video_path),  # 使用绝对路径
                "文件名称": file_name,
                "文件大小": f"{file_size:.2f}",
                "视频总帧数": frame_count,
                "帧率": fps,
                "分辨率": f"{width}x{height}",
                "时长": duration,
                "是否包含音频": has_audio,
                "音频时长": audio_duration if has_audio else None,
                "音频采样率": audio_fps if has_audio else None,
                "分析用时": analysis_duration,
                "total_bitrate": total_bitrate,
                "audio_info": {
                    "audio_bitrate": audio_bitrate
                }
            }

            self.finished.emit(result)

        except Exception as e:
            self.logger.error(f"视频分析出错: {str(e)}", exc_info=True)
            self.error.emit(f"视频分析失败: {str(e)}")

    def stop(self):
        self.logger.info("停止视频分析")
        self.terminate()
        self.wait()
