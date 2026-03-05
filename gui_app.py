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
from config_models import AnalysisSettings
from config_models import AnalysisSettings
from timeline_manager import TranscriptManager
from event_dispatcher import EventEmitter
from analysis_controller import AnalysisController
from ui_block_editor import UIBlockEditor

class CustomModelApp:
    @property
    def results_data(self):
        return self.transcript_manager.get_all()
        
    @results_data.setter
    def results_data(self, val):
        if val == []:
            self.transcript_manager.clear()
    def __init__(self, root):
        self.root = root
        self.root.title("VAD AI Studio v25 (Vision Integrated)")
        self.root.geometry("1300x850")
        self.engine = HyperTranscriptionEngine()
        self.video_editor = VideoEditor()
        self.player = None
        self.stop_event = threading.Event()
        self.transcript_manager = TranscriptManager()
        self.current_video_path = None
        self.is_seeking = False
        self.ICON_PLAY = chr(9654); self.ICON_PAUSE = chr(9208)
        self.dispatcher = EventEmitter()
        self.controller = AnalysisController(self.engine, self.video_editor, self.transcript_manager, self.dispatcher)
        self.setup_ui()
        self.player = VideoPlayer(self.video_canvas.winfo_id())
        self.bind_keys()
        self.bind_events()
        self.load_engine_async()
        self.update_loop()

    def bind_events(self):
        self.dispatcher.on("progress", lambda x: self.root.after(0, lambda: self._on_progress(x)))
        self.dispatcher.on("add_row", lambda x: self.root.after(0, lambda: self._on_add_row(x)))
        self.dispatcher.on("complete", lambda x: self.root.after(0, lambda: self._on_complete(x)))
        self.dispatcher.on("message", lambda x: self.root.after(0, lambda: messagebox.showinfo("완료", x["text"])))
        self.dispatcher.on("error", lambda x: self.root.after(0, lambda: messagebox.showerror("오류", x["text"])))
        self.dispatcher.on("ghost_defense", lambda x: self.root.after(0, lambda: [self.reset_action_button(), self.btn_stop.config(state=tk.DISABLED)]))

    def _on_progress(self, task):
        self.progress_var.set(task["value"]); self.lbl_status.config(text=task["text"])
        
    def _on_add_row(self, task):
        self.tree.insert("", "end", values=(task["i"], self.format_time(task['s']), self.format_time(task['e']), task['t']))
        
    def _on_complete(self, task):
        self.lbl_status.config(text=task["text"], fg="#27ae60"); self.progress_var.set(100)
        self.btn_analyze.config(state=tk.NORMAL)
        if task.get("is_vad"): 
            self.save_frame.pack(fill=tk.X, pady=5, before=self.lbl_status)
            for b in [self.btn_fast_save, self.btn_pro_save, self.btn_xml_save]: b.config(state=tk.NORMAL)
        
        if task.get("is_whisper"): self.apply_preview_subtitles()
        self.btn_stop.config(state=tk.DISABLED)

    def setup_ui(self):
        self.main_paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=6)
        self.main_paned.pack(fill=tk.BOTH, expand=True)

        left_f = tk.Frame(self.main_paned, bg="#1a1a1a")
        self.main_paned.add(left_f, minsize=400, width=500)

        self.video_canvas = tk.Frame(left_f, bg="black")
        self.video_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=(2, 5))
        self.video_canvas.bind("<Button-1>", lambda e: self.toggle_play())

        self.seek_var = tk.DoubleVar()
        self.seek_bar = tk.Scale(left_f, from_=0, to=1000, orient=tk.HORIZONTAL, variable=self.seek_var, showvalue=0, bg="#1a1a1a")
        self.seek_bar.pack(fill=tk.X, padx=10, pady=2)
        self.seek_bar.bind("<ButtonPress-1>", self.on_seek_start)
        self.seek_bar.bind("<ButtonRelease-1>", self.on_seek_release)
        self.seek_bar.bind("<B1-Motion>", self.on_seek_motion)

        ctrl = tk.Frame(left_f, bg="#2d2d2d", pady=10)
        ctrl.pack(fill=tk.X)
        
        bg_f = tk.Frame(ctrl, bg="#2d2d2d")
        bg_f.pack(expand=True)
        
        tk.Button(bg_f, text=chr(9194)+" 5s", command=lambda: self.skip_time(-5000), bg="#444", fg="white", width=8).pack(side=tk.LEFT, padx=10)
        self.btn_play = tk.Button(bg_f, text=self.ICON_PLAY, command=self.toggle_play, width=8, bg="#27ae60", fg="white")
        self.btn_play.pack(side=tk.LEFT, padx=10)
        tk.Button(bg_f, text="5s "+chr(9193), command=lambda: self.skip_time(5000), bg="#444", fg="white", width=8).pack(side=tk.LEFT, padx=10)

        self.lbl_time = tk.Label(ctrl, text="00:00 / 00:00", bg="#2d2d2d", fg="white")
        self.lbl_time.pack(side=tk.RIGHT, padx=20)
        right_f = tk.Frame(self.main_paned, padx=15); self.main_paned.add(right_f, minsize=600, width=800)
        af = tk.LabelFrame(right_f, text=" 분석 및 편집 설정 ", padx=10, pady=10); af.pack(fill=tk.X, pady=10)
        tk.Button(af, text="영상 파일 선택", command=self.on_select_video, bg="#34495e", fg="white", font=("bold")).pack(fill=tk.X, pady=5)
        model_f = tk.Frame(af); model_f.pack(fill=tk.X, pady=5)
        tk.Label(model_f, text="AI 모델:").pack(side=tk.LEFT)
        self.ai_model_var = tk.StringVar(value="large-v3-turbo (기본)")
        self.ai_model_combo = ttk.Combobox(model_f, textvariable=self.ai_model_var, values=["large-v3-turbo (기본)", "models/whisper-medium-ko-zeroth (Medium-Zeroth)"], state="readonly", width=60)
        self.ai_model_combo.pack(side=tk.LEFT, padx=5)
        self.ai_model_var.trace_add("write", lambda *args: self.reset_action_button())
        mf = tk.Frame(af); mf.pack(fill=tk.X)
        self.mode_var = tk.StringVar(value="대사 변환 및 컷편집 (종합)")
        self.mode_combo = ttk.Combobox(mf, textvariable=self.mode_var, values=["자연어-대사 변환", "대사 변환 및 컷편집", "깜놀 구간 탐색", "무음 제거 편집 (VAD)", "자동 챕터 분할 (CLIP)"], state="readonly", width=30)
        self.mode_combo.pack(side=tk.LEFT, padx=5, pady=10); self.mode_var.trace_add("write", lambda *args: self.reset_action_button())
        self.btn_analyze = tk.Button(af, text="분석 시작", command=self.on_start_analysis, bg="#2980b9", fg="white", font=("bold"), pady=12); self.btn_analyze.pack(fill=tk.X, pady=5)
        self.btn_stop = tk.Button(af, text="작업 중지", command=self.on_stop_action, bg="#c0392b", fg="white", font=("bold"), state=tk.DISABLED); self.btn_stop.pack(fill=tk.X, pady=2)
        self.save_frame = tk.Frame(right_f); self.save_frame.pack(fill=tk.X, pady=2); self.save_frame.pack_forget()
        tk.Label(self.save_frame, text="[ 영상 및 타임라인 내보내기 ]", fg="#8e44ad", font=("bold", 10)).pack(pady=2)
        btn_box = tk.Frame(self.save_frame); btn_box.pack(fill=tk.X, pady=2)
        self.btn_fast_save = tk.Button(btn_box, text="🚀 초고속 인코딩", command=lambda: self.start_export(fast=True), bg="#8e44ad", fg="white", pady=8); self.btn_fast_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.btn_pro_save = tk.Button(btn_box, text="🎯 정밀 인코딩", command=lambda: self.start_export(fast=False), bg="#2c3e50", fg="white", pady=8); self.btn_pro_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.btn_xml_save = tk.Button(btn_box, text="🎬 타임라인 XML", command=self.on_export_xml, bg="#16a085", fg="white", pady=8); self.btn_xml_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.lbl_status = tk.Label(right_f, text="준비됨", fg="#27ae60", font=("bold", 10)); self.lbl_status.pack(fill=tk.X, pady=5)
        self.progress_var = tk.DoubleVar(); ttk.Progressbar(right_f, variable=self.progress_var).pack(fill=tk.X, pady=5)
        list_f = tk.Frame(right_f); list_f.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # [시니어 최적화] 리스트 뷰와 드래그&드롭 블록 뷰를 전환할 수 있는 노트북(탭) 시스템
        self.notebook = ttk.Notebook(list_f)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.tab_tree = tk.Frame(self.notebook)
        self.notebook.add(self.tab_tree, text="기본 리스트 뷰")
        self.tab_canvas = tk.Frame(self.notebook)
        self.notebook.add(self.tab_canvas, text="[실험] 단어 블록 마법진 (Drag & Drop)")

        self.tree = ttk.Treeview(self.tab_tree, columns=("no", "start", "end", "text"), show="headings"); self.tree.heading("no", text="No"); self.tree.heading("start", text="시작"); self.tree.heading("end", text="종료"); self.tree.heading("text", text="내용/길이"); self.tree.column("no", width=40, anchor=tk.CENTER); self.tree.column("start", width=80, anchor=tk.CENTER); self.tree.column("end", width=80, anchor=tk.CENTER); self.tree.column("text", width=250); sc = ttk.Scrollbar(self.tab_tree, orient=tk.VERTICAL, command=self.tree.yview); self.tree.configure(yscrollcommand=sc.set); self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sc.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.block_editor = UIBlockEditor(self.tab_canvas, self.root, self.transcript_manager, self.player, self.rebuild_tree_and_render)
        def _on_tab_changed(e):
            idx = self.notebook.index(self.notebook.select())
            if idx == 1:
                self.block_editor.render_block_view()
                # [시니어 최적화] 리스트 스크롤 비율을 캔버스로 복사
                self.block_editor.block_canvas.yview_moveto(self.tree.yview()[0])
            elif idx == 0:
                # [시니어 최적화] 캔버스 스크롤 비율을 리스트로 복사
                self.tree.yview_moveto(self.block_editor.block_canvas.yview()[0])
        self.notebook.bind("<<NotebookTabChanged>>", _on_tab_changed)
        
        # 우클릭 메뉴 및 이벤트 바인딩 복구
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="시작 지점으로 이동", command=self.jump_to_start)
        self.menu.add_command(label="종료 지점으로 이동", command=self.jump_to_end)
        self.menu.add_separator()
        self.menu.add_command(label="대사 수정하기", command=self.edit_selected_text)
        
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        self.tree.bind("<Button-3>", self.show_context_menu)
        opt = tk.LabelFrame(right_f, text=" 상세 설정 ", padx=10, pady=10); opt.pack(fill=tk.X, pady=5)
        
        # [시니어 최적화] UI 공간 절약을 위해 가로 배치 및 간격 조절
        set_f = tk.Frame(opt); set_f.pack(fill=tk.X, pady=2)
        tk.Label(set_f, text="빔 사이즈:").pack(side=tk.LEFT)
        self.beam_size_var = tk.IntVar(value=5)
        tk.Scale(set_f, from_=1, to=15, orient=tk.HORIZONTAL, variable=self.beam_size_var, showvalue=1, length=120).pack(side=tk.LEFT, padx=5)
        
        chk_f = tk.Frame(opt); chk_f.pack(fill=tk.X, pady=2)
        self.use_denoise_var = tk.BooleanVar(value=False); tk.Checkbutton(chk_f, text="소음 제거", variable=self.use_denoise_var).pack(side=tk.LEFT)
        self.use_dominant_var = tk.BooleanVar(value=False); tk.Checkbutton(chk_f, text="주인공만", variable=self.use_dominant_var, fg="#e67e22").pack(side=tk.LEFT, padx=10)
        
        # 언어 선택을 위로 올림
        tk.Label(chk_f, text="언어:").pack(side=tk.LEFT, padx=(10, 0))
        self.lang_var = tk.StringVar(value="한국어 (ko)")
        self.lang_combo = ttk.Combobox(chk_f, textvariable=self.lang_var, values=["한국어 (ko)", "영어 (en)", "일본어 (ja)", "중국어 (zh)", "자동 감지 (auto)"], state="readonly", width=12)
        self.lang_combo.pack(side=tk.LEFT, padx=5)

        vad_f = tk.Frame(opt); vad_f.pack(fill=tk.X, pady=2)
        
        # [시니어 추가] VAD 필터 옵션
        self.use_silero_vad_var = tk.BooleanVar(value=True)
        tk.Checkbutton(vad_f, text="외부 VAD (Silero)", variable=self.use_silero_vad_var).pack(side=tk.LEFT)
        self.use_whisper_vad_var = tk.BooleanVar(value=True)
        tk.Checkbutton(vad_f, text="내부 VAD (Whisper)", variable=self.use_whisper_vad_var).pack(side=tk.LEFT, padx=5)

        tk.Label(vad_f, text="무음/패딩:").pack(side=tk.LEFT, padx=(10, 0))
        self.silence_dur_var = tk.DoubleVar(value=2.0); tk.Entry(vad_f, textvariable=self.silence_dur_var, width=4).pack(side=tk.LEFT, padx=2)
        tk.Label(vad_f, text="s /").pack(side=tk.LEFT)
        self.speech_pad_var = tk.DoubleVar(value=0.1); tk.Entry(vad_f, textvariable=self.speech_pad_var, width=4).pack(side=tk.LEFT, padx=2)
        tk.Label(vad_f, text="s").pack(side=tk.LEFT, padx=(10, 0))
        self.vad_threshold_var = tk.DoubleVar(value=0.35)
        tk.Scale(vad_f, from_=0.1, to=0.9, resolution=0.05, orient=tk.HORIZONTAL, variable=self.vad_threshold_var, showvalue=1, length=100).pack(side=tk.LEFT, padx=5)

        adv_f = tk.Frame(opt); adv_f.pack(fill=tk.X, pady=2)
        
        # [시니어 추가] 하드웨어 가속 선택기
        tk.Label(adv_f, text="가속:").pack(side=tk.LEFT)
        self.device_var = tk.StringVar(value="자동 감지 (auto)")
        ttk.Combobox(adv_f, textvariable=self.device_var, values=["자동 감지 (auto)", "NVIDIA (cuda)", "Apple Mac (mps)", "CPU (멀티코어)"], state="readonly", width=14).pack(side=tk.LEFT, padx=5)

        self.remove_punctuation_var = tk.BooleanVar(value=True)
        tk.Checkbutton(adv_f, text="문장 부호 소거 (.,-)", variable=self.remove_punctuation_var, fg="#34495e").pack(side=tk.LEFT, padx=5)

        lf = tk.Frame(opt)
        lf.pack(fill=tk.X, pady=2)
        
        tk.Label(lf, text="대사 길이:").pack(side=tk.LEFT)
        self.max_len_int = tk.IntVar(value=50)
        self.max_len_str = tk.StringVar(value="50")
        
        tk.Scale(lf, from_=10, to=50, orient=tk.HORIZONTAL, variable=self.max_len_int, showvalue=0, command=lambda v: self.max_len_str.set(str(v)), length=150).pack(side=tk.LEFT, padx=5)
        tk.Entry(lf, textvariable=self.max_len_str, width=3).pack(side=tk.LEFT)
        
        self.export_format = tk.StringVar(value="SRT")
        tk.Button(lf, text="자막 내보내기", command=self.export_subtitles, bg="#e67e22", fg="white", padx=10).pack(side=tk.RIGHT, padx=5)
        ttk.Combobox(lf, textvariable=self.export_format, values=["SRT", "VTT", "TXT", "CSV"], state="readonly", width=6).pack(side=tk.RIGHT, padx=5)

    def bind_keys(self): self.root.bind("<space>", lambda e: self.toggle_play()); self.root.bind("<Left>", lambda e: self.skip_time(-5000)); self.root.bind("<Right>", lambda e: self.skip_time(5000))
    def format_time(self, t_sec):
        m = int(t_sec // 60)
        s = t_sec % 60
        return f"{m:02d}:{s:05.2f}"
    
    def parse_time(self, t_str):
        if ":" in str(t_str):
            parts = str(t_str).split(":")
            if len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
        return float(str(t_str).replace("s", ""))

    def load_engine_async(self): threading.Thread(target=self.controller.init_engine, daemon=True).start()

    def reset_action_button(self): self.save_frame.pack_forget(); self.btn_analyze.config(text="분석 시작", command=self.on_start_analysis, bg="#2980b9", state=tk.NORMAL); self.btn_fast_save.config(state=tk.NORMAL); self.btn_pro_save.config(state=tk.NORMAL); self.btn_xml_save.config(state=tk.NORMAL)
    def on_select_video(self):
        p = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov *.flv")])
        if p:
            self.current_video_path = p
            
            # 기존에 로드된 자막 파일 연결 끊기
            if hasattr(self, 'preview_srt_path'):
                self.preview_srt_path = None
                
            if self.player.load_video(p):
                self.lbl_status.config(text="영상 로드됨: " + os.path.basename(p), fg="#2980b9")
                self.reset_action_button()
                
                if hasattr(self, 'preview_srt_path') and getattr(self, 'preview_srt_path') and os.path.exists(self.preview_srt_path):
                    self.root.after(300, self.apply_preview_subtitles)
            else:
                from tkinter import messagebox
                messagebox.showerror("Error", "영상을 불러올 수 없습니다.")


    def on_stop_action(self):
        if self.stop_event and not self.stop_event.is_set(): 
            self.stop_event.set()
            # 큐를 완전 증발 시킬 필요가 없어짐 (이벤트 구독 구조이므로 stop_event가 set되면 컨트롤러가 발송 중단함)
            self.lbl_status.config(text="■ 작업 중지 중... 완전 종료 대기", fg="red")
            self.btn_stop.config(state=tk.DISABLED)
            self.root.after(1500, lambda: self.reset_action_button() or self.lbl_status.config(text="작업 중지됨", fg="red"))

    def on_start_analysis(self):
        mode = self.mode_var.get()
        selected_model = self.ai_model_var.get().split(" ")[0]
        self.engine.set_model_id(selected_model)
        
        # [시니어 추가] 분석 옵션 수집
        try: min_sil_ms, pad_ms = int(self.silence_dur_var.get() * 1000), int(self.speech_pad_var.get() * 1000)
        except: min_sil_ms, pad_ms = 2000, 250
        
        device_val = self.device_var.get()
        if "auto" in device_val: mapped_dev = "auto"
        elif "cuda" in device_val: mapped_dev = "cuda"
        elif "mps" in device_val: mapped_dev = "mps"
        else: mapped_dev = "cpu"

        analysis_options = AnalysisSettings(
            beam_size=self.beam_size_var.get(),
            use_denoise=self.use_denoise_var.get(),
            use_dominant=self.use_dominant_var.get(),
            language=self.lang_var.get().split("(")[-1].replace(")", "").strip(),
            vad_threshold=self.vad_threshold_var.get(),
            min_silence_ms=min_sil_ms,
            speech_pad_ms=pad_ms,
            use_word_timestamps=True,
            use_whisper_vad=self.use_whisper_vad_var.get(),
            use_silero_vad=self.use_silero_vad_var.get(),
            remove_punctuation=getattr(self, 'remove_punctuation_var', tk.BooleanVar(value=False)).get(),
            device_mode=mapped_dev
        )
        
        self.stop_event = threading.Event(); self.btn_analyze.config(state=tk.DISABLED); self.btn_stop.config(state=tk.NORMAL); self.progress_var.set(0); self.results_data = []
        for i in self.tree.get_children(): self.tree.delete(i)
        
        # 컨트롤러에 작업 이관
        max_chars = self.max_len_int.get()
        threading.Thread(target=self.controller.run_analysis, args=(self.current_video_path, self.stop_event, mode, min_sil_ms, pad_ms, max_chars, analysis_options), daemon=True).start()

    def start_export(self, fast=True):
        media_info = self.video_editor.get_media_info(self.current_video_path); ext = os.path.splitext(self.current_video_path)[1].lower().strip('.')
        save_path = filedialog.asksaveasfilename(defaultextension=f".{ext if ext in ['mp4','mkv','mov','avi'] else 'mp4'}", filetypes=[("Video File", f"*.{ext}")], initialfile=f"cut_{os.path.basename(self.current_video_path)}")
        if save_path:
            for b in [self.btn_fast_save, self.btn_pro_save, self.btn_xml_save]: b.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL); self.progress_var.set(0)
            settings = {'v_codec': media_info.get('v_codec', 'h264'), 'a_codec': media_info.get('a_codec', 'aac'), 'v_bitrate': f"{media_info.get('v_bitrate', 5000000) // 1000}k", 'a_bitrate': f"{media_info.get('a_bitrate', 128000) // 1000}k", 'fast_mode': fast}
            threading.Thread(target=self.controller.run_editing, args=(self.current_video_path, save_path, self.results_data, self.stop_event, settings), daemon=True).start()

    def on_export_xml(self):
        save_path = filedialog.asksaveasfilename(defaultextension=".xml", filetypes=[("Final Cut Pro XML", "*.xml")], initialfile=f"Timeline_{os.path.splitext(os.path.basename(self.current_video_path))[0]}.xml")
        if save_path:
            try:
                media_info = self.video_editor.get_media_info(self.current_video_path); real_fps = media_info.get("fps", 30.0)
                if self.video_editor.export_premiere_xml(self.current_video_path, self.results_data, save_path, fps=real_fps): messagebox.showinfo("완료", f"XML 생성 완료:\n{save_path}")
                else: messagebox.showerror("오류", "XML 생성 실패")
            except Exception as e: messagebox.showerror("오류", str(e))



    def on_tree_click(self, e):
        item = self.tree.identify_row(e.y); col = self.tree.identify_column(e.x)
        if item:
            val = self.tree.item(item)['values']
            if col == '#4':
                bbox = self.tree.bbox(item, '#4')
                if bbox:
                    x, y, w, h = bbox
                    self._open_editor(item, x, y, max(w, 200), max(h, 20), e.x - x)
            else:
                try:
                    # 시작 시간 클릭(#2) vs 종료 시간 클릭(#3) 분기 처리
                    if col == '#3': t_sec = self.parse_time(val[2])
                    else: t_sec = self.parse_time(val[1])
                    self.player.set_time(int(t_sec * 1000))
                except: pass
            
    def edit_selected_text(self):
        sel = self.tree.selection()
        if not sel: return
        item = sel[0]
        bbox = self.tree.bbox(item, '#4')
        if bbox:
            x, y, w, h = bbox
            self._open_editor(item, x, y, max(w, 200), max(h, 20))


    def rebuild_tree_and_render(self):
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self.results_data):
            self.tree.insert("", "end", values=(i+1, self.format_time(r.get('s',0)), self.format_time(r.get('e',0)), r.get('t','')))
        if getattr(self, "notebook", None) and self.notebook.index(self.notebook.select()) == 1:
            self.block_editor.render_block_view()
        self.apply_preview_subtitles(force_reload=True)



    def _open_editor(self, item, x, y, w, h, click_x=None):
        val = self.tree.item(item)['values']
        text = str(val[3] if len(val) > 3 else "")
        entry = tk.Entry(self.tree)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, text)
        entry.focus()

        # [시니어 최적화] 사용자가 클릭한 x 좌표를 계산하여 해당 글자 사이에 커서 파킹
        if click_x is not None:
            def _set_cursor():
                idx = entry.index(f"@{max(0, click_x)}")
                entry.icursor(idx)
            self.root.after(10, _set_cursor)
        else:
            entry.selection_range(0, tk.END)

        # [시니어 모션 트래킹] 스크롤 시 텍스트 입력창이 원본 셀 위치를 실시간으로 따라가도록 추적
        def _track_position():
            if not entry.winfo_exists(): return
            bbox = self.tree.bbox(item, '#4')
            if bbox:
                nx, ny, nw, nh = bbox
                entry.place(x=nx, y=ny, width=max(nw, 200), height=max(nh, 20))
            else:
                entry.place(x=-9999, y=-9999) # 화면 밖으로 스크롤 시 임시 숨김 처리
            self.root.after(15, _track_position)
        
        _track_position()

        # [시니어 최적화] 실시간 타이핑 반영 (Debounced)
        def _on_key_release(event):
            if event.keysym in ['Return', 'Escape']: return
            if hasattr(self, '_edit_debounce_timer') and self._edit_debounce_timer:
                self.root.after_cancel(self._edit_debounce_timer)
            self._edit_debounce_timer = self.root.after(300, save_edit_live)

        def save_edit_live():
            if not entry.winfo_exists(): return
            new_text = entry.get()
            self.tree.set(item, column='#4', value=new_text)
            try:
                idx = int(self.tree.item(item)['values'][0]) - 1
                if 0 <= idx < len(self.results_data):
                    self.results_data[idx]['t'] = new_text
                    # [시니어 최적화] 텍스트 수정 발생 시 기존 단어 블록(배열) 파쇄를 통해 탭2 진입 시 자동 분할 재계산 유도
                    self.results_data[idx].pop('words', None)
                    self.apply_preview_subtitles(force_reload=True)
            except: pass

        entry.bind('<KeyRelease>', _on_key_release)

        def save_edit(event=None):
            if hasattr(self, '_edit_debounce_timer') and self._edit_debounce_timer:
                self.root.after_cancel(self._edit_debounce_timer)
            save_edit_live()
            try: entry.destroy()
            except: pass

        entry.bind('<Return>', save_edit)
        entry.bind('<FocusOut>', save_edit)
        entry.bind('<Escape>', lambda ev: entry.destroy())

    def jump_to_start(self):
        sel = self.tree.selection()
        if sel: self.player.set_time(int(float(str(self.tree.item(sel[0])['values'][1]).replace('s','')) * 1000))
    def jump_to_end(self):
        sel = self.tree.selection()
        if sel: self.player.set_time(int(float(str(self.tree.item(sel[0])['values'][2]).replace('s','')) * 1000))
    def show_context_menu(self, e):
        item = self.tree.identify_row(e.y)
        if item: self.tree.selection_set(item); self.menu.post(e.x_root, e.y_root)
    def apply_preview_subtitles(self, force_reload=False):
        if not self.results_data or not self.player: return
        try:
            # [시니어 최적화] VLC 경로 캐싱 무효화를 위한 A/B 핑퐁 시스템 적용 (파일명이 같으면 VLC가 로드하지 않음)
            suffix = "A" if getattr(self, "_ping_pong", False) else "B"
            self._ping_pong = not getattr(self, "_ping_pong", False)
            srt_name = os.path.abspath(f"temp_preview_{suffix}.srt")
            
            with open(srt_name, "w", encoding="utf-8") as f:
                for i, r in enumerate(self.results_data):
                    s_r, e_r = r['s'], r['e']
                    # [시니어 최적화] 다음 자막과 시간이 겹치거나 맞닿으면 0.05초(50ms) 갭을 추가하여 자막 분리 깜박임 구현
                    if i < len(self.results_data) - 1 and e_r >= self.results_data[i+1]['s']: e_r = max(s_r + 0.1, self.results_data[i+1]['s'] - 0.05)
                    s = time.strftime('%H:%M:%S', time.gmtime(s_r)) + f",{int((s_r%1)*1000):03d}"; e = time.strftime('%H:%M:%S', time.gmtime(e_r)) + f",{int((e_r%1)*1000):03d}"; f.write(f"{i+1}\n{s} --> {e}\n{r['t']}\n\n")
            
            self.player.set_subtitle(srt_name)
            
            # [시니어 최적화] 실시간 타이핑 시 VLC가 일시정지 상태라면, 강제로 현재 시간에 다시 제자리 점프하여 프레임을 새로고침
            if force_reload and not self.player.is_playing():
                curr = self.player.get_time()
                if curr >= 0:
                    self.player.set_time(curr)
        except: pass
    def toggle_play(self):
        if self.player: is_p = self.player.toggle_play(); self.btn_play.config(text=self.ICON_PAUSE if is_p else self.ICON_PLAY)
    def skip_time(self, ms): 
        if self.player: self.player.skip(ms)
    def on_seek_start(self, e):
        self.is_seeking = True
        self._was_playing_before_seek = self.player.is_playing() if self.player else False
        if self.player:
            self.player.set_mute(True)
            if not self._was_playing_before_seek:
                self.player.toggle_play() # 강제 갱신을 위해 재생 시작
        self._update_seek_from_mouse(e)
    def on_seek_motion(self, e):
        if self.is_seeking: self._update_seek_from_mouse(e)
    def on_seek_release(self, e):
        if self.is_seeking: self._update_seek_from_mouse(e)
        self.is_seeking = False
        if self.player:
            if getattr(self, '_was_playing_before_seek', False):
                self.player.play() # 원래 재생 상태였다면 재생
            else:
                self.player.pause() # 원래 일시정지 상태였다면 정지
            # 즉시 뮤트 해제 시 소리가 튈 수 있어 약간의 딜레이
            self.root.after(100, lambda: self.player.set_mute(False) if self.player else None)
    def _update_seek_from_mouse(self, e):
        try:
            w = self.seek_bar.winfo_width()
            if w > 0 and self.player:
                pos = max(0.0, min(1.0, e.x / w))
                self.player.set_position(pos)
                self.seek_var.set(pos * 1000)
        except: pass
    def update_loop(self):
        if self.player:
            if not self.is_seeking:
                pos = self.player.get_position()
                if pos >= 0: self.seek_var.set(pos * 1000)
            curr_ms, total_ms = self.player.get_time(), self.player.get_length()
            if curr_ms >= 0 and total_ms > 0:
                c_m, c_s = divmod(int(curr_ms/1000), 60); t_m, t_s = divmod(int(total_ms/1000), 60); self.lbl_time.config(text=f"{c_m:02d}:{c_s:02d} / {t_m:02d}:{t_s:02d}")
            if hasattr(self, 'btn_play'): self.btn_play.config(text=self.ICON_PAUSE if self.player.is_playing() else self.ICON_PLAY)
        self.root.after(500, self.update_loop)
    def export_subtitles(self):
        if not self.results_data: return
        fmt = self.export_format.get(); ext = "." + fmt.lower(); initial = os.path.splitext(os.path.basename(self.current_video_path))[0]; file_path = filedialog.asksaveasfilename(defaultextension=ext, initialfile=initial, filetypes=[(fmt, "*" + ext)])
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                if fmt == "SRT":
                    for i, r in enumerate(self.results_data):
                        s_r, e_r = r['s'], r['e']
                        if i < len(self.results_data) - 1 and e_r >= self.results_data[i+1]['s']: e_r = max(s_r + 0.1, self.results_data[i+1]['s'] - 0.05)
                        s = time.strftime('%H:%M:%S', time.gmtime(s_r)) + f",{int((s_r%1)*1000):03d}"; e = time.strftime('%H:%M:%S', time.gmtime(e_r)) + f",{int((e_r%1)*1000):03d}"; f.write(f"{i+1}\n{s} --> {e}\n{r['t']}\n\n")
                elif fmt == "TXT":
                    for r in self.results_data: f.write(f"[{round(r['s'], 2)}s] {r['t']}\n")
            messagebox.showinfo("완료", "저장되었습니다.")
