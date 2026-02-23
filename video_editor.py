import os
import subprocess
import time
import re
import imageio_ffmpeg

class VideoEditor:
    def __init__(self):
        self.ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

    def cut_silence(self, input_video, output_video, segments, stop_event=None, progress_callback=None):
        """음성 구간만 추출하여 합침 (진행률 및 예상 대기 시간 지원)"""
        if not segments: return False
        
        # 1. 구간 병합 및 총 출력 길이 계산
        merged = []
        total_out_duration = 0
        curr_s, curr_e = segments[0]['s'], segments[0]['e']
        for next_seg in segments[1:]:
            if next_seg['s'] - curr_e < 2.0:
                curr_e = max(curr_e, next_seg['e'])
            else:
                merged.append((curr_s, curr_e))
                total_out_duration += (curr_e - curr_s)
                curr_s, curr_e = next_seg['s'], next_seg['e']
        merged.append((curr_s, curr_e))
        total_out_duration += (curr_e - curr_s)

        # 2. FFmpeg Filter Complex 생성
        filter_complex = ""
        concat_input = ""
        for i, (start, end) in enumerate(merged):
            s_adj, e_adj = max(0, start - 0.05), end + 0.05
            filter_complex += f"[0:v]trim=start={s_adj}:end={e_adj},setpts=PTS-STARTPTS[v{i}]; "
            filter_complex += f"[0:a]atrim=start={s_adj}:end={e_adj},asetpts=PTS-STARTPTS[a{i}]; "
            concat_input += f"[v{i}][a{i}]"
        
        filter_complex += f"{concat_input}concat=n={len(merged)}:v=1:a=1[outv][outa]"

        cmd = [
            self.ffmpeg_path, "-y", "-i", input_video,
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-threads", "8",
            output_video
        ]

        try:
            start_real_time = time.time()
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                     universal_newlines=True, encoding='utf-8', errors='replace')
            
            time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")

            while True:
                if stop_event and stop_event.is_set():
                    process.terminate()
                    return False
                
                line = process.stdout.readline()
                if not line: break
                
                if progress_callback and total_out_duration > 0:
                    match = time_pattern.search(line)
                    if match:
                        hours, mins, secs = map(float, match.groups())
                        current_processed_time = hours * 3600 + mins * 60 + secs
                        
                        # 진행률 계산
                        progress = min(100, int((current_processed_time / total_out_duration) * 100))
                        
                        # ETA 계산
                        elapsed_real_time = time.time() - start_real_time
                        if current_processed_time > 0 and elapsed_real_time > 1:
                            # 속도 = 처리된 영상 시간 / 실제 경과 시간
                            speed = current_processed_time / elapsed_real_time
                            remaining_video_time = total_out_duration - current_processed_time
                            eta_seconds = int(remaining_video_time / speed)
                        else:
                            eta_seconds = -1 # 아직 계산 불가
                            
                        progress_callback(progress, eta_seconds)

            process.wait()
            return process.returncode == 0
        except Exception as e:
            print(f"FFmpeg Error: {e}")
            return False
