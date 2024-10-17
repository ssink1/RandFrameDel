import cv2
import random
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
import time
import logging
import os
from processors.audio_processor import AudioProcessor
from moviepy.editor import VideoFileClip, AudioFileClip
import subprocess
import json

# 尝试导入 win32process 和 win32con，如果失败则设置为 None
try:
    from win32com import win32process
    from win32com import win32con
except ImportError:
    win32process = None
    win32con = None

class VideoProcessor(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str, list, dict)
    frame_deleted_signal = pyqtSignal(int, list)
    current_second_signal = pyqtSignal(int)
    info_signal = pyqtSignal(str)

    def __init__(self, input_path, output_path, interval_range, delete_frames, fps, audio_info, frame_count, original_video_info):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.interval_range = interval_range
        self.delete_frames = delete_frames
        self.fps = fps
        self.audio_info = audio_info
        self.frame_count = frame_count
        self.original_video_info = original_video_info
        self.is_running = True
        self.deleted_frames_info = []
        self.logger = logging.getLogger(__name__)
        self.audio_processor = AudioProcessor()

    def run(self):
        self.logger.info("开始视频处理")
        start_time = time.time()
        try:
            self.logger.info("开始视频处理步骤")
            if self.is_running:
                self._process_video()
            self.logger.info("视频处理步骤完成")
            if self.is_running:
                self._process_audio()
            self.logger.info("音频处理步骤完成")
            if self.is_running:
                self._merge_video_audio()
            self.logger.info("视频音频合并步骤完成")
        except Exception as e:
            self.logger.error(f"视频处理出错: {str(e)}", exc_info=True)
            self.finished.emit(f"处理失败: {str(e)}", [], {})
        else:
            end_time = time.time()
            processing_time = end_time - start_time
            self.logger.info(f"处理完成，用时: {processing_time:.2f}秒")
            final_video_info = self.get_final_video_info(self.output_path)
            final_video_info['processing_time'] = processing_time
            self.finished.emit("处理完成。", self.deleted_frames_info, final_video_info)

    def _process_video(self):
        cap = cv2.VideoCapture(self.input_path)
        out = None
        try:
            if not cap.isOpened():
                raise IOError(f"无法打开视频文件: {self.input_path}")

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            temp_video_path = self.output_path.rsplit('.', 1)[0] + '_temp_video.mp4'
            
            out = cv2.VideoWriter(temp_video_path, fourcc, self.fps, (width, height))
            if not out.isOpened():
                raise IOError(f"无法创建临时视频文件: {temp_video_path}")

            start_sec, end_sec = map(int, self.interval_range.split('-'))
            self.deleted_frames_info = []

            # 预先计算要删除的帧
            total_seconds = int(self.frame_count / self.fps)
            current_sec = random.randint(max(1, start_sec), end_sec)
            while current_sec < total_seconds:
                if current_sec not in [info[0] for info in self.deleted_frames_info]:
                    frames_in_this_second = min(int(self.fps), self.frame_count - current_sec * int(self.fps))
                    frames_to_delete = random.sample(range(frames_in_this_second), min(self.delete_frames, frames_in_this_second))
                    global_frames_to_delete = [frame + current_sec * int(self.fps) for frame in frames_to_delete]
                    if frames_to_delete:
                        self.deleted_frames_info.append((current_sec, global_frames_to_delete))
                        self.frame_deleted_signal.emit(current_sec, global_frames_to_delete)
                        self.current_second_signal.emit(current_sec)
                
                interval = random.randint(max(1, start_sec), end_sec)
                current_sec += interval

            # 使用numpy优化帧处理
            frames_to_delete_set = set(frame for _, frames in self.deleted_frames_info for frame in frames)
            for i in range(self.frame_count):
                if not self.is_running:
                    break
                ret, frame = cap.read()
                if not ret:
                    break
                
                if i not in frames_to_delete_set:
                    out.write(frame)
                
                if i % (self.frame_count // 100) == 0:
                    self.progress.emit(int((i + 1) / self.frame_count * 100), "视频处理")

            self.progress.emit(100, "视频处理")
        finally:
            cap.release()
            if out is not None:
                out.release()

    def _process_audio(self):
        if self.audio_info["has_audio"] and self.is_running:
            try:
                self.info_signal.emit("开始处理音频...")
                audio_path = self.audio_info.get("audio_path")
                if not audio_path or not os.path.exists(audio_path):
                    self.info_signal.emit("正在从视频中提取音频...")
                    video = VideoFileClip(self.input_path)
                    audio = video.audio
                    audio_path = self.output_path.rsplit('.', 1)[0] + '_temp_audio.wav'
                    audio.write_audiofile(audio_path, logger=None)
                    video.close()

                deleted_frames_flat = [frame for _, frames in self.deleted_frames_info for frame in frames]
                
                def audio_progress_callback(progress, remaining_time):
                    self.progress.emit(int(progress * 100), f"音频处理 - 预计剩余: {int(remaining_time)}秒")

                processed_audio = self.audio_processor.process_audio(
                    audio_path, 
                    deleted_frames_flat, 
                    self.fps, 
                    self.frame_count,
                    audio_progress_callback
                )
                processed_audio_path = self.output_path.rsplit('.', 1)[0] + '_temp_processed_audio.wav'
                processed_audio.export(processed_audio_path, format="wav")
                self.info_signal.emit("音频处理完成")

            except Exception as e:
                self.logger.error(f"音频处理失败: {str(e)}")
                self.info_signal.emit(f"音频处理失败: {str(e)}")

    def _merge_video_audio(self):
        if not self.is_running:
            return
        self.info_signal.emit("开始合成视频和音频...")
        try:
            temp_video_path = self.output_path.rsplit('.', 1)[0] + '_temp_video.mp4'
            processed_audio_path = self.output_path.rsplit('.', 1)[0] + '_temp_processed_audio.wav'

            # 获取原视频的比特率信息
            total_bitrate = self.original_video_info.get('total_bitrate', '5000k')
            audio_bitrate = self.original_video_info.get('audio_info', {}).get('audio_bitrate', '192k')
            
            # 计算视频比特率
            video_bitrate = int(total_bitrate.replace('k', '')) - int(audio_bitrate.replace('k', ''))
            video_bitrate = f"{video_bitrate}k"

            # 使用 FFmpeg 合并视频和音频，并设置比特率
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', temp_video_path,
                '-i', processed_audio_path,
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-b:v', video_bitrate,
                '-maxrate', video_bitrate,
                '-bufsize', f"{int(video_bitrate.replace('k', ''))*2}k",
                '-c:a', 'aac',
                '-b:a', audio_bitrate,
                '-strict', 'experimental',
                '-y',
                '-loglevel', 'error',
                self.output_path
            ]

            # 使用 CREATE_NO_WINDOW 标志来隐藏控制台窗口
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            # 读取 FFmpeg 的输出并更新进度
            for line in process.stderr:
                if "time=" in line and "bitrate=" in line:
                    try:
                        time_str = line.split("time=")[1].split()[0]
                        current_time = sum(float(x) * 60 ** i for i, x in enumerate(reversed(time_str.split(":"))))
                        progress = int((current_time / self.original_video_info['时长']) * 100)
                        self.progress.emit(progress, "视频音频合成")
                        self.info_signal.emit(f"合成进度: {progress}%")
                    except:
                        pass

            stdout, stderr = process.communicate()

            if process.returncode != 0:
                error_message = f"FFmpeg 合并失败。错误信息：\n{stderr}"
                raise Exception(error_message)

            self.info_signal.emit("视频和音频合成完成")
            self.progress.emit(100, "处理完成")
            
            final_video_info = self.get_final_video_info(self.output_path)
            self.finished.emit("处理完成。", self.deleted_frames_info, final_video_info)
        except Exception as e:
            self.logger.error(f"合成视频和音频时出错: {str(e)}", exc_info=True)
            self.info_signal.emit(f"合成视频和音频时出错: {str(e)}")
            self.progress.emit(100, "处理出错")

    def stop(self):
        self.is_running = False
        self.wait()
        self.cleanup()

    def get_final_video_info(self, video_path):
        if not os.path.exists(video_path):
            return {
                "path": video_path,
                "error": "输出文件不存在"
            }
        
        try:
            video = VideoFileClip(video_path)
            cap = cv2.VideoCapture(video_path)
            
            info = {
                "path": video_path,
                "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                "fps": cap.get(cv2.CAP_PROP_FPS),
                "duration": video.duration,
                "size": int(os.path.getsize(video_path) / (1024 * 1024)),  # 转换为MB并取整
                "resolution": video.size,
                "has_audio": video.audio is not None,
                "total_bitrate": self.original_video_info.get('total_bitrate'),
            }
            
            if info["has_audio"]:
                info["audio_fps"] = video.audio.fps
                info["audio_duration"] = video.audio.duration
                info["audio_channels"] = video.audio.nchannels if hasattr(video.audio, 'nchannels') else None
                info["audio_bitrate"] = self.original_video_info.get('audio_info', {}).get('audio_bitrate')
            
            video.close()
            cap.release()
            return info
        except Exception as e:
            self.logger.error(f"获取最终视频信息时出错: {str(e)}", exc_info=True)
            return {
                "path": video_path,
                "error": f"无法获取视频信息: {str(e)}"
            }

    def cleanup(self):
        self.logger.info("开始清理 VideoProcessor 资源")
        if hasattr(self, 'video_clip'):
            self.video_clip.close()
        if hasattr(self, 'audio_clip'):
            self.audio_clip.close()
        self.logger.info("VideoProcessor 资源清理完成")

    def _run_ffmpeg_command(self, command):
        # 使用subprocess.STARTUPINFO来隐藏ffmpeg窗口
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo
        )
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            raise Exception(f"FFmpeg命令执行失败: {stderr.decode()}")
