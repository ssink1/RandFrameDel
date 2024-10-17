from pydub import AudioSegment
import numpy as np
import logging
import time

class AudioProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def process_audio(self, audio_path, deleted_frames, fps, total_frames, progress_callback):
        try:
            self.logger.info("开始处理音频")
            audio = AudioSegment.from_wav(audio_path)
            
            # 计算每帧对应的音频毫秒数
            ms_per_frame = 1000 / fps
            
            # 创建一个新的音频段
            processed_audio = AudioSegment.empty()
            
            current_ms = 0
            start_time = time.time()

            for frame in range(total_frames):
                if frame not in deleted_frames:
                    # 如果这一帧不需要删除，添加到处理后的音频中
                    frame_audio = audio[current_ms:current_ms + ms_per_frame]
                    processed_audio += frame_audio
                
                current_ms += ms_per_frame

                if frame % 100 == 0:  # 每处理100帧更新一次进度
                    progress = (frame + 1) / total_frames
                    elapsed_time = time.time() - start_time
                    estimated_total_time = elapsed_time / progress
                    remaining_time = estimated_total_time - elapsed_time
                    progress_callback(progress, remaining_time)

            self.logger.info("音频处理完成")
            return processed_audio

        except Exception as e:
            self.logger.error(f"音频处理出错: {str(e)}", exc_info=True)
            raise
