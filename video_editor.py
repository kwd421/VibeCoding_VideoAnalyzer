import os
import subprocess
import time
import re
import imageio_ffmpeg
from typing import List, Dict, Tuple, Optional, Callable

class VideoEditor:
    """비디오 편집 엔진 (Match Source, Stream Copy 및 프리미어/리졸브 완벽 호환 XML 지원)"""
    
    def __init__(self):
        self.ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        self.threads = 8 

    @staticmethod
    def get_merged_segments_info(segments: List[Dict], gap_threshold: float = 2.0) -> Tuple[List[Tuple[float, float]], float]:
        if not segments: return [], 0.0
        sorted_segs = sorted(segments, key=lambda x: x['s'])
        merged, total_duration = [], 0.0
        if not sorted_segs: return [], 0.0
        curr_s, curr_e = sorted_segs[0]['s'], sorted_segs[0]['e']
        for next_seg in sorted_segs[1:]:
            if next_seg['s'] - curr_e < gap_threshold:
                curr_e = max(curr_e, next_seg['e'])
            else:
                merged.append((curr_s, curr_e)); total_duration += (curr_e - curr_s)
                curr_s, curr_e = next_seg['s'], next_seg['e']
        merged.append((curr_s, curr_e)); total_duration += (curr_e - curr_s)
        return merged, total_duration

    def get_media_info(self, video_path: str) -> Dict:
        """[시니어 리팩토링] ffprobe JSON 모드를 사용하여 견고하게 메타데이터 추출"""
        info = {
            "v_bitrate": 5000000, "a_bitrate": 128000, 
            "v_codec": "h264", "a_codec": "aac", "is_lossless": False,
            "file_size_mb": os.path.getsize(video_path) / (1024 * 1024),
            "total_duration": 1.0,
            "fps": 30.0 
        }
        
        try:
            import json
            ffprobe_path = self.ffmpeg_path.replace("ffmpeg.exe", "ffprobe.exe") if "ffmpeg.exe" in self.ffmpeg_path else self.ffmpeg_path.replace("ffmpeg", "ffprobe")
            if not os.path.exists(ffprobe_path):
                raise FileNotFoundError("ffprobe not found")

            cmd = [
                ffprobe_path, 
                "-v", "quiet", 
                "-print_format", "json", 
                "-show_format", 
                "-show_streams", 
                video_path
            ]
            
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            process = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', startupinfo=startupinfo)
            data = json.loads(process.stdout)
            
            if 'format' in data:
                f_data = data['format']
                info["total_duration"] = float(f_data.get('duration', 1.0))
                total_rate = int(f_data.get('bit_rate', 5000000))
                info['v_bitrate'] = int(total_rate * 0.85)
                info['a_bitrate'] = 128000
                
            for stream in data.get('streams', []):
                if stream['codec_type'] == 'video':
                    info['v_codec'] = stream.get('codec_name', 'h264')
                    if 'avg_frame_rate' in stream:
                        num, den = map(int, stream['avg_frame_rate'].split('/'))
                        if den > 0: info['fps'] = num / den
                elif stream['codec_type'] == 'audio':
                    info['a_codec'] = stream.get('codec_name', 'aac')
                    if 'bit_rate' in stream:
                        info['a_bitrate'] = int(stream['bit_rate'])
        except Exception as e:
            # 실패 시 기존 정규식 방식으로 Fallback
            cmd = [self.ffmpeg_path, "-i", video_path]
            try:
                process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8', errors='replace')
                _, stderr = process.communicate()
                import re
                fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", stderr)
                if fps_match: info["fps"] = float(fps_match.group(1))
                dur_match = re.search(r"Duration:\s+(\d+):(\d+):(\d+\.\d+)", stderr)
                if dur_match:
                    h, m, s = map(float, dur_match.groups())
                    info["total_duration"] = h * 3600 + m * 60 + s
                br_match = re.search(r"bitrate:\s+(\d+)\s+kb/s", stderr)
                if br_match:
                    total_br = int(br_match.group(1)) * 1000
                    info["v_bitrate"] = int(total_br * 0.9); info["a_bitrate"] = int(total_br * 0.1)
                if "h264" in stderr.lower(): info["v_codec"] = "h264"
                elif "hevc" in stderr.lower() or "h265" in stderr.lower(): info["v_codec"] = "h265"
            except: pass
            
        return info

    def export_premiere_xml(self, video_path: str, segments: List[Dict], output_xml: str, fps: float = 30.0) -> bool:
        """[시니어 최적화] 프리미어 프로/다빈치 리졸브 완벽 호환 FCP 7 XML 생성"""
        merged, _ = self.get_merged_segments_info(segments)
        if not merged: return False

        video_name = os.path.basename(video_path)
        video_full_path = os.path.abspath(video_path)
        
        xml_header = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4">
    <sequence>
        <name>Rough Cut - {video_name}</name>
        <duration>0</duration>
        <rate>
            <timebase>{int(fps)}</timebase>
            <ntsc>{"TRUE" if fps % 30 != 0 else "FALSE"}</ntsc>
        </rate>
        <media>
            <video>
                <track>
"""
        v_clips, a_clips, current_out = "", "", 0
        for i, (start, end) in enumerate(merged):
            dur_f = int((end - start) * fps); in_f = int(start * fps); out_f = int(end * fps)
            clip_content = f"""
                    <clipitem id="clipitem-{{ID}}">
                        <name>{video_name}</name>
                        <duration>{int(999999 * fps)}</duration>
                        <rate><timebase>{int(fps)}</timebase></rate>
                        <in>{in_f}</in><out>{out_f}</out>
                        <start>{current_out}</start><end>{current_out + dur_f}</end>
                        <file id="file-1">
                            <name>{video_name}</name>
                            <pathurl>file://localhost/{video_full_path.replace(os.sep, '/')}</pathurl>
                            <media>
                                <video><duration>{int(999999 * fps)}</duration></video>
                                <audio><duration>{int(999999 * fps)}</duration></audio>
                            </media>
                        </file>
                    </clipitem>"""
            v_clips += clip_content.replace("{ID}", f"{i}")
            a_clips += clip_content.replace("{ID}", f"a{i}")
            current_out += dur_f

        xml_footer = f"""
                </track>
            </video>
            <audio>
                <track>
{a_clips}
                </track>
            </audio>
        </media>
    </sequence>
</xmeml>"""
        try:
            with open(output_xml, "w", encoding="utf-8") as f: f.write(xml_header + v_clips + xml_footer)
            return True
        except Exception as e:
            print(f"XML Export Error: {e}"); return False

    def cut_silence(self, input_video, output_video, segments, stop_event=None, progress_callback=None,
                    v_codec="h264", a_codec="aac", v_bitrate="5000k", a_bitrate="128k", fast_mode=True) -> bool:
        merged, total_out_duration = self.get_merged_segments_info(segments)
        if not merged or total_out_duration <= 0: return False

        if fast_mode:
            unique_id = int(time.time())
            temp_dir = os.path.abspath(f"temp_fast_{unique_id}"); os.makedirs(temp_dir, exist_ok=True)
            list_file_path = os.path.join(temp_dir, "concat.txt")
            try:
                with open(list_file_path, "w", encoding="utf-8") as f:
                    for i, (start, end) in enumerate(merged):
                        if stop_event and stop_event.is_set(): return False
                        s_adj, e_adj = max(0, start - 0.05), end + 0.05
                        chunk_path = os.path.join(temp_dir, f"chunk_{i:04d}.ts")
                        cmd_cut = [
                            self.ffmpeg_path, "-y", "-ss", str(s_adj), "-to", str(e_adj), 
                            "-i", input_video, "-c", "copy", 
                            "-map", "0:v:0", "-map", "0:a:0", 
                            "-avoid_negative_ts", "make_zero", "-start_at_zero",
                            "-f", "mpegts", chunk_path
                        ]
                        subprocess.run(cmd_cut, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                        f.write(f"file '{chunk_path.replace('\\', '/')}'\n")
                cmd_concat = [self.ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", list_file_path, "-c", "copy", output_video]
                return self._execute_ffmpeg(cmd_concat, total_out_duration, stop_event, progress_callback)
            except Exception as e: print(f"[FastMode Error] {e}"); return False
            finally:
                try:
                    for entry in os.listdir(temp_dir): os.remove(os.path.join(temp_dir, entry))
                    os.rmdir(temp_dir)
                except: pass
        else:
            v_filters, a_filters, concat_input = [], [], ""
            for i, (start, end) in enumerate(merged):
                s_adj, e_adj = max(0, start - 0.05), end + 0.05
                v_filters.append(f"[0:v]trim=start={s_adj}:end={e_adj},setpts=PTS-STARTPTS[v{i}]")
                a_filters.append(f"[0:a]atrim=start={s_adj}:end={e_adj},asetpts=PTS-STARTPTS[a{i}]")
                concat_input += f"[v{i}][a{i}]"
            filter_complex = "; ".join(v_filters + a_filters) + f"; {concat_input}concat=n={len(merged)}:v=1:a=1[outv][outa]"
            script_path = os.path.abspath(f"temp_filter_{int(time.time())}.txt")
            with open(script_path, "w", encoding="utf-8") as f: f.write(filter_complex)
            v_map = {"h264": "libx264", "h265": "libx265", "hevc": "libx265", "av1": "libsvtav1", "vp9": "libvpx-vp9"}
            a_map = {"aac": "aac", "mp3": "libmp3lame", "opus": "libopus", "flac": "flac"}
            cmd = [self.ffmpeg_path, "-y", "-i", input_video, "-filter_complex_script", script_path, "-map", "[outv]", "-map", "[outa]", "-c:v", v_map.get(v_codec.lower(), "libx264"), "-b:v", v_bitrate, "-preset", "faster", "-threads", str(self.threads), "-c:a", a_map.get(a_codec.lower(), "aac"), "-b:a", a_bitrate, output_video]
            try: return self._execute_ffmpeg(cmd, total_out_duration, stop_event, progress_callback)
            finally:
                if os.path.exists(script_path): os.remove(script_path)

    def _execute_ffmpeg(self, cmd, total_duration, stop_event, progress_callback):
        try:
            start_real_time = time.time()
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, encoding='utf-8', errors='replace')
            info_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+).*speed=\s*(\d+\.\d+)x")
            while True:
                if stop_event and stop_event.is_set(): process.terminate(); return False
                line = process.stdout.readline()
                if not line: break
                if progress_callback and total_duration > 0:
                    match = info_pattern.search(line)
                    if match:
                        h, m, s, speed = map(float, match.groups()); curr_proc = h * 3600 + m * 60 + s
                        progress = min(100, int((curr_proc / total_duration) * 100))
                        if speed > 0.01: eta = int((total_duration - curr_proc) / speed)
                        else:
                            elapsed = time.time() - start_real_time
                            eta = int((total_duration - curr_proc) / (curr_proc / elapsed)) if curr_proc > 0 else -1
                        progress_callback(progress, eta)
            process.wait(); return process.returncode == 0
        except Exception as e: print(f"[VideoEditor] Exception: {e}"); return False
