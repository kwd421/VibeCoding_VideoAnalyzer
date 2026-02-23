import os
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import vlc
from engine_core import HyperTranscriptionEngine
from video_editor import VideoEditor
from video_player import VideoPlayer

class CustomModelApp:
    def __init__(self, root):
        self.root = root
        self.root.title("VAD AI Studio v21 (Fixed & Stable)")
        self.root.geometry("1300x850")
        
        self.engine = HyperTranscriptionEngine()
        self.video_editor = VideoEditor()
        self.player = None
        
        self.stop_event = threading.Event()
        self.results_data = []
        self.current_video_path = None
        self.is_seeking = False
        self.ICON_PLAY = chr(9654)
        self.ICON_PAUSE = chr(9208)
        
        self.setup_ui()
        self.player = VideoPlayer(self.video_canvas.winfo_id())
        self.bind_keys()
        self.load_engine_async()

    def setup_ui(self):
        self.main_paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=6)
        self.main_paned.pack(fill=tk.BOTH, expand=True)

        # 왼쪽: 비디오 플레이어 영역
        left_f = tk.Frame(self.main_paned, bg="#1a1a1a")
        self.main_paned.add(left_f, minsize=750)

        self.video_canvas = tk.Frame(left_f, bg="black")
        self.video_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.video_canvas.bind("<Button-1>", lambda e: self.toggle_play())

        self.seek_var = tk.DoubleVar()
        self.seek_bar = tk.Scale(left_f, from_=0, to=1000, orient=tk.HORIZONTAL, variable=self.seek_var, showvalue=0, bg="#1a1a1a")
        self.seek_bar.pack(fill=tk.X, padx=10, pady=2)
        self.seek_bar.bind("<ButtonPress-1>", self.on_seek_start)
        self.seek_bar.bind("<ButtonRelease-1>", self.on_seek_release)

        ctrl = tk.Frame(left_f, bg="#2d2d2d", pady=10)
        ctrl.pack(fill=tk.X)
        bg_f = tk.Frame(ctrl, bg="#2d2d2d"); bg_f.pack(expand=True)
        tk.Button(bg_f, text=chr(9194)+" 5s", command=lambda: self.skip_time(-5000), bg="#444", fg="white", width=8).pack(side=tk.LEFT, padx=10)
        self.btn_play = tk.Button(bg_f, text=self.ICON_PLAY, command=self.toggle_play, width=8, bg="#27ae60", fg="white"); self.btn_play.pack(side=tk.LEFT, padx=10)
        tk.Button(bg_f, text="5s "+chr(9193), command=lambda: self.skip_time(5000), bg="#444", fg="white", width=8).pack(side=tk.LEFT, padx=10)
        self.lbl_time = tk.Label(ctrl, text="00:00 / 00:00", bg="#2d2d2d", fg="white"); self.lbl_time.pack(side=tk.RIGHT, padx=20)

        # 오른쪽: 제어 패널
        right_f = tk.Frame(self.main_paned, padx=15)
        self.main_paned.add(right_f, minsize=450)

        af = tk.LabelFrame(right_f, text=" 분석 및 편집 설정 ", padx=10, pady=10)
        af.pack(fill=tk.X, pady=10)
        tk.Button(af, text="영상 파일 선택", command=self.on_select_video, bg="#34495e", fg="white", font=("bold")).pack(fill=tk.X, pady=5)
        
        mf = tk.Frame(af); mf.pack(fill=tk.X)
        self.mode_var = tk.StringVar(value="자연어-대사 변환")
        ttk.Combobox(mf, textvariable=self.mode_var, values=["자연어-대사 변환", "깜놀 구간 탐색 (초고속)", "무음 제거 편집 (VAD)"], state="readonly", width=30).pack(side=tk.LEFT, padx=5, pady=10)

        self.btn_analyze = tk.Button(af, text="분석 시작", command=self.on_start_analysis, bg="#2980b9", fg="white", font=("bold"), pady=12, state=tk.DISABLED)
        self.btn_analyze.pack(fill=tk.X, pady=5)

        self.btn_stop = tk.Button(af, text="작업 중지", command=self.on_stop_action, bg="#c0392b", fg="white", font=("bold"), state=tk.DISABLED); self.btn_stop.pack(fill=tk.X, pady=2)

        # 상태 표시 및 프로그레스바
        self.lbl_status = tk.Label(right_f, text="준비됨", fg="#27ae60", font=("bold", 10)); self.lbl_status.pack(fill=tk.X, pady=5)
        self.progress_var = tk.DoubleVar(); ttk.Progressbar(right_f, variable=self.progress_var).pack(fill=tk.X, pady=5)

        # 결과 리스트 (Treeview) - 유실되었던 부분 복구
        list_f = tk.Frame(right_f)
        list_f.pack(fill=tk.BOTH, expand=True, pady=10)
        
        columns = ("no", "start", "end", "text")
        self.tree = ttk.Treeview(list_f, columns=columns, show="headings")
        self.tree.heading("no", text="No"); self.tree.heading("start", text="시작"); self.tree.heading("end", text="종료"); self.tree.heading("text", text="내용/길이")
        self.tree.column("no", width=40, anchor=tk.CENTER); self.tree.column("start", width=80, anchor=tk.CENTER); self.tree.column("end", width=80, anchor=tk.CENTER); self.tree.column("text", width=250)
        
        sc = ttk.Scrollbar(list_f, orient=tk.VERTICAL, command=self.tree.yview); self.tree.configure(yscrollcommand=sc.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sc.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 우클릭 메뉴 및 이벤트 바인딩
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="시작 지점으로 이동", command=self.jump_to_start)
        self.menu.add_command(label="종료 지점으로 이동", command=self.jump_to_end)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Button-1>", self.on_tree_click)

        # 자막 설정 프레임
        opt = tk.LabelFrame(right_f, text=" 상세 설정 ", padx=10, pady=10)
        opt.pack(fill=tk.X, pady=5)
        
        lf = tk.Frame(opt); lf.pack(fill=tk.X)
        tk.Label(lf, text="대사 길이:").pack(side=tk.LEFT)
        self.max_len_int = tk.IntVar(value=50); self.max_len_str = tk.StringVar(value="50")
        tk.Scale(lf, from_=10, to=50, orient=tk.HORIZONTAL, variable=self.max_len_int, showvalue=0, command=lambda v: self.max_len_str.set(str(v))).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Entry(lf, textvariable=self.max_len_str, width=4).pack(side=tk.LEFT)

        self.export_format = tk.StringVar(value="SRT")
        ex = tk.Frame(opt, pady=5); ex.pack(fill=tk.X)
        ttk.Combobox(ex, textvariable=self.export_format, values=["SRT", "VTT", "TXT", "CSV"], state="readonly", width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(ex, text="자막 내보내기", command=self.export_subtitles, bg="#e67e22", fg="white").pack(side=tk.LEFT, padx=5)

        self.update_loop()

    def bind_keys(self):
        self.root.bind("<space>", lambda e: self.toggle_play())
        self.root.bind("<Left>", lambda e: self.skip_time(-5000))
        self.root.bind("<Right>", lambda e: self.skip_time(5000))

    def load_engine_async(self): threading.Thread(target=self._init_engine, daemon=True).start()
    def _init_engine(self):
        try: self.engine.get_model(); self.root.after(0, lambda: self.lbl_status.config(text="엔진 준비 완료", fg="#27ae60"))
        except Exception as e: messagebox.showerror("Error", f"엔진 로드 실패: {e}")

    def reset_action_button(self):
        self.btn_analyze.config(text="분석 시작", command=self.on_start_analysis, bg="#2980b9", state=tk.NORMAL)

    def on_select_video(self):
        p = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov *.flv")])
        if p:
            self.current_video_path = p
            if self.player.load_video(p):
                self.lbl_status.config(text="영상 로드됨: " + os.path.basename(p), fg="#2980b9")
                self.reset_action_button()
            else: messagebox.showerror("Error", "영상을 불러올 수 없습니다.")

    def on_stop_action(self):
        if self.stop_event: self.stop_event.set(); self.lbl_status.config(text="중지 요청됨...", fg="red"); self.btn_stop.config(state=tk.DISABLED)

    def on_start_analysis(self):
        self.stop_event = threading.Event(); self.btn_analyze.config(state=tk.DISABLED); self.btn_stop.config(state=tk.NORMAL)
        self.progress_var.set(0); self.results_data = []
        for i in self.tree.get_children(): self.tree.delete(i)
        threading.Thread(target=self.run_analysis, args=(self.current_video_path, self.stop_event), daemon=True).start()

    def run_analysis(self, p, stop_ev):
        tmp = "refactored_temp.wav"; mode = self.mode_var.get(); max_chars = self.max_len_int.get()
        try:
            self.root.after(0, lambda: self.lbl_status.config(text="오디오 추출 중...", fg="orange"))
            self.engine.extract_audio(p, tmp)
            if stop_ev.is_set(): return
            audio_data, avg_rms, duration = self.engine.get_audio_info(tmp)
            if stop_ev.is_set(): return

            if "무음 제거" in mode:
                self.root.after(0, lambda: self.lbl_status.config(text="VAD 분석 중...", fg="blue"))
                self.results_data = self.engine.detect_speech_vad(audio_data, stop_ev)
                for i, r in enumerate(self.results_data):
                    dur = r['e'] - r['s']
                    self.root.after(0, self.add_row, i+1, r['s'], r['e'], f"음성 ({dur:.2f}s)")
            elif "깜놀" in mode:
                self.root.after(0, lambda: self.lbl_status.config(text="피크 구간 감지 중...", fg="blue"))
                peaks = self.engine.detect_peaks_only(audio_data, avg_rms, stop_ev)
                for i, (s, e) in enumerate(peaks):
                    if stop_ev.is_set(): break
                    self.results_data.append({'s': s, 'e': e, 't': f"[볼륨 피크 {i+1}]"})
                    self.root.after(0, self.add_row, i+1, s, e, f"피크 감지")
            else:
                gen, total_dur = self.engine.transcribe_stream_raw(tmp, stop_ev)
                for i, (start, end, text) in enumerate(gen):
                    if stop_ev.is_set(): break
                    self.results_data.append({'s': start, 'e': end, 't': text})
                    self.root.after(0, self.add_row, len(self.results_data), start, end, text)
                    self.root.after(0, lambda v=(start/total_dur)*100: [self.progress_var.set(v), self.lbl_status.config(text=f"분석 중 ({int(v)}%)")])

            if not stop_ev.is_set():
                if "무음 제거" in mode:
                    self.root.after(0, lambda: [
                        self.lbl_status.config(text="분석 완료 (저장 가능)", fg="#27ae60"),
                        self.progress_var.set(100),
                        self.btn_analyze.config(text="무음 제거 영상 저장", command=self.on_save_edited_video, bg="#8e44ad", state=tk.NORMAL),
                        self.btn_stop.config(state=tk.DISABLED)
                    ])
                else:
                    self.root.after(0, lambda: [
                        self.lbl_status.config(text="분석 완료", fg="#27ae60"), 
                        self.progress_var.set(100),
                        self.apply_preview_subtitles(),
                        self.btn_analyze.config(state=tk.NORMAL),
                        self.btn_stop.config(state=tk.DISABLED)
                    ])
        except Exception as ex:
            if not stop_ev.is_set(): self.root.after(0, lambda e=ex: messagebox.showerror("Error", f"분석 오류: {str(e)}"))
        finally:
            if os.path.exists(tmp): os.remove(tmp)
            if stop_ev.is_set(): self.root.after(0, lambda: [self.reset_action_button(), self.btn_stop.config(state=tk.DISABLED)])

    def add_row(self, i, s, e, t):
        self.tree.insert("", "end", values=(i, f"{round(s, 2)}s", f"{round(e, 2)}s", t))

    def on_save_edited_video(self):
        if not self.results_data: return
        save_path = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4 Video", "*.mp4")], initialfile=f"cut_{os.path.basename(self.current_video_path)}")
        if save_path:
            self.btn_analyze.config(state=tk.DISABLED); self.btn_stop.config(state=tk.NORMAL); self.progress_var.set(0)
            threading.Thread(target=self.run_editing, args=(save_path,), daemon=True).start()

    def run_editing(self, out_path):
        def update_progress(v, eta):
            eta_str = f" - 남은 시간: {int(eta//60)}분 {int(eta%60)}초" if eta >= 0 else ""
            self.root.after(0, lambda: [self.progress_var.set(v), self.lbl_status.config(text=f"인코딩 중 ({v}%){eta_str}")])
        try:
            success = self.video_editor.cut_silence(self.current_video_path, out_path, self.results_data, self.stop_event, update_progress)
            if success: messagebox.showinfo("성공", f"저장 완료:\n{out_path}"); self.root.after(0, self.reset_action_button)
        except Exception as e: messagebox.showerror("Error", f"편집 오류: {str(e)}")
        finally: self.root.after(0, lambda: [self.lbl_status.config(text="작업 완료", fg="#27ae60"), self.btn_stop.config(state=tk.DISABLED), self.btn_analyze.config(state=tk.NORMAL)])

    def on_tree_click(self, e):
        region = self.tree.identify_region(e.x, e.y)
        if region == "cell":
            column = self.tree.identify_column(e.x); item = self.tree.identify_row(e.y)
            if item:
                values = self.tree.item(item)['values']
                try:
                    t_sec = float(str(values[2]).replace('s','')) if column == "#3" else float(str(values[1]).replace('s',''))
                    self.player.set_time(int(t_sec * 1000))
                    if not self.player.is_playing(): self.player.toggle_play()
                except: pass

    def show_context_menu(self, e):
        item = self.tree.identify_row(e.y)
        if item: self.tree.selection_set(item); self.menu.post(e.x_root, e.y_root)

    def jump_to_start(self):
        sel = self.tree.selection()
        if sel: self.player.set_time(int(float(str(self.tree.item(sel)['values'][1]).replace('s','')) * 1000))

    def jump_to_end(self):
        sel = self.tree.selection()
        if sel: self.player.set_time(int(float(str(self.tree.item(sel)['values'][2]).replace('s','')) * 1000))

    def apply_preview_subtitles(self):
        if not self.results_data or not self.player: return
        temp_srt = "temp_preview.srt"
        try:
            with open(temp_srt, "w", encoding="utf-8") as f:
                for i, r in enumerate(self.results_data):
                    start = time.strftime('%H:%M:%S', time.gmtime(r['s'])) + f",{int((r['s']%1)*1000):03d}"
                    end = time.strftime('%H:%M:%S', time.gmtime(r['e'])) + f",{int((r['e']%1)*1000):03d}"
                    f.write(f"{i+1}\n{start} --> {end}\n{r['t']}\n\n")
            self.player.set_subtitle(os.path.abspath(temp_srt))
        except: pass

    def toggle_play(self):
        if self.player: is_p = self.player.toggle_play(); self.btn_play.config(text=self.ICON_PAUSE if is_p else self.ICON_PLAY)

    def skip_time(self, ms): 
        if self.player: self.player.skip(ms)

    def on_seek_start(self, e):
        self.is_seeking = True
        try:
            w = self.seek_bar.winfo_width()
            if w > 0: self.player.set_position(max(0, min(1, e.x/w)))
        except: pass

    def on_seek_release(self, e): self.is_seeking = False; self.player.toggle_play() if not self.player.is_playing() else None

    def update_loop(self):
        if self.player:
            if not self.is_seeking:
                pos = self.player.get_position()
                if pos >= 0: self.seek_var.set(pos * 1000)
            curr_ms, total_ms = self.player.get_time(), self.player.get_length()
            if curr_ms >= 0 and total_ms > 0:
                c_m, c_s = divmod(int(curr_ms/1000), 60); t_m, t_s = divmod(int(total_ms/1000), 60)
                self.lbl_time.config(text=f"{c_m:02d}:{c_s:02d} / {t_m:02d}:{t_s:02d}")
            if hasattr(self, 'btn_play'): self.btn_play.config(text=self.ICON_PAUSE if self.player.is_playing() else self.ICON_PLAY)
        self.root.after(500, self.update_loop)

    def export_subtitles(self):
        if not self.results_data: return
        fmt = self.export_format.get(); ext = "." + fmt.lower()
        initial = os.path.splitext(os.path.basename(self.current_video_path))[0]
        file_path = filedialog.asksaveasfilename(defaultextension=ext, initialfile=initial, filetypes=[(fmt, "*" + ext)])
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                if fmt == "SRT":
                    for i, r in enumerate(self.results_data):
                        start = time.strftime('%H:%M:%S', time.gmtime(r['s'])) + f",{int((r['s']%1)*1000):03d}"
                        end = time.strftime('%H:%M:%S', time.gmtime(r['e'])) + f",{int((r['e']%1)*1000):03d}"
                        f.write(f"{i+1}\n{start} --> {end}\n{r['t']}\n\n")
                elif fmt == "TXT":
                    for r in self.results_data: f.write(f"[{round(r['s'],2)}s] {r['t']}\n")
            messagebox.showinfo("완료", "저장되었습니다.")
