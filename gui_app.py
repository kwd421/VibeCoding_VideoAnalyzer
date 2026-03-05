import os
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, font as tkfont
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
        self.root.title("VAD AI Studio v26")
        self.root.geometry("1300x850")
        self.root.configure(bg="#1c1c1e")
        
        # [Apple 디자인 시스템] 글로벌 색상 팔레트
        self.C = {
            'bg':       '#1c1c1e',  # 배경 (System Background)
            'bg2':      '#2c2c2e',  # 2차 배경 (Secondary)
            'bg3':      '#3a3a3c',  # 3차 배경 (Tertiary)
            'surface':  '#48484a',  # 표면 (Surface)
            'border':   '#545456',  # 테두리
            'text':     '#f5f5f7',  # 기본 텍스트
            'text2':    '#98989d',  # 보조 텍스트
            'accent':   '#0a84ff',  # 액센트 블루
            'green':    '#30d158',  # 성공/완료
            'red':      '#ff453a',  # 경고/삭제
            'orange':   '#ff9f0a',  # 주의
            'purple':   '#bf5af2',  # 보라
            'teal':     '#64d2ff',  # 정보
        }
        C = self.C
        
        # [Apple 디자인] ttk 스타일 테마 구축
        style = ttk.Style()
        style.theme_use('clam')
        
        _font = ('Segoe UI', 10)
        _font_s = ('Segoe UI', 9)
        _font_h = ('Segoe UI', 11, 'bold')
        
        style.configure('.', background=C['bg2'], foreground=C['text'], font=_font, borderwidth=0)
        style.configure('TFrame', background=C['bg2'])
        style.configure('TLabel', background=C['bg2'], foreground=C['text'], font=_font)
        style.configure('TLabelframe', background=C['bg2'], foreground=C['text'], font=_font_h)
        style.configure('TLabelframe.Label', background=C['bg2'], foreground=C['accent'], font=_font_h)
        
        style.configure('Treeview', background=C['bg'], foreground=C['text'], fieldbackground=C['bg'],
                         rowheight=28, font=_font_s, borderwidth=0)
        style.configure('Treeview.Heading', background=C['bg3'], foreground=C['text2'],
                         font=('Segoe UI', 9, 'bold'), borderwidth=0, relief='flat')
        style.map('Treeview', background=[('selected', C['accent'])], foreground=[('selected', '#ffffff')])
        style.map('Treeview.Heading', background=[('active', C['surface'])])
        
        style.configure('TNotebook', background=C['bg'], borderwidth=0)
        style.configure('TNotebook.Tab', background=C['bg3'], foreground=C['text2'],
                         font=_font_s, padding=[12, 6], borderwidth=0)
        style.map('TNotebook.Tab', background=[('selected', C['accent'])], foreground=[('selected', '#ffffff')])
        
        style.configure('TCombobox', fieldbackground=C['bg3'], background=C['surface'],
                         foreground=C['text'], arrowcolor=C['text2'], borderwidth=1)
        style.map('TCombobox', fieldbackground=[('readonly', C['bg3'])], foreground=[('readonly', C['text'])])
        
        style.configure('Horizontal.TProgressbar', troughcolor=C['bg3'], background=C['accent'],
                         borderwidth=0, thickness=6)
        style.configure('TScrollbar', background=C['bg3'], troughcolor=C['bg'], borderwidth=0, arrowcolor=C['text2'])
        
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
        self.lbl_status.config(text=task["text"], fg=self.C['green']); self.progress_var.set(100)
        self.btn_analyze.config(state=tk.NORMAL)
        if task.get("is_vad"): 
            self.save_frame.pack(fill=tk.X, pady=5, before=self.lbl_status)
            for b in [self.btn_fast_save, self.btn_pro_save, self.btn_xml_save]: b.config(state=tk.NORMAL)
        
        if task.get("is_whisper"): self.apply_preview_subtitles()
        self.btn_stop.config(state=tk.DISABLED)

    def setup_ui(self):
        C = self.C
        self.main_paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.FLAT, sashwidth=4, bg=C['border'])
        self.main_paned.pack(fill=tk.BOTH, expand=True)

        left_f = tk.Frame(self.main_paned, bg=C['bg'])
        self.main_paned.add(left_f, minsize=400, width=500)

        self._video_aspect = 9 / 16  # 기본 16:9 비율 (h/w)
        self.video_canvas = tk.Frame(left_f, bg="black", height=281, width=500)
        self.video_canvas.pack_propagate(False)
        self.video_canvas.pack(fill=tk.X, padx=5, pady=(2, 5))
        self.video_canvas.bind("<Button-1>", lambda e: self.toggle_play())
        
        # [시니어 최적화] 패널 폭 변경 시 영상 비율 유지하며 높이를 동적으로 재계산
        def _on_canvas_resize(e):
            new_w = e.width
            if new_w > 10:
                new_h = int(new_w * self._video_aspect)
                if new_h > 10 and abs(new_h - self.video_canvas.winfo_height()) > 5:
                    self.video_canvas.config(height=new_h)
        self.video_canvas.bind("<Configure>", _on_canvas_resize)

        self.seek_var = tk.DoubleVar()
        self.seek_bar = tk.Scale(left_f, from_=0, to=1000, orient=tk.HORIZONTAL, variable=self.seek_var, showvalue=0, bg=C['bg'], highlightthickness=0, troughcolor=C['bg3'], fg=C['accent'], sliderrelief=tk.FLAT)
        self.seek_bar.pack(fill=tk.X, padx=10, pady=2)
        self.seek_bar.bind("<ButtonPress-1>", self.on_seek_start)
        self.seek_bar.bind("<ButtonRelease-1>", self.on_seek_release)
        self.seek_bar.bind("<B1-Motion>", self.on_seek_motion)

        ctrl = tk.Frame(left_f, bg=C['bg2'], pady=8)
        ctrl.pack(fill=tk.X)
        
        bg_f = tk.Frame(ctrl, bg=C['bg2'])
        bg_f.pack(expand=True)
        
        _btn_cfg = dict(font=('Segoe UI', 9), relief=tk.FLAT, bd=0, padx=8, pady=4)
        tk.Button(bg_f, text=chr(9194)+" 5s", command=lambda: self.skip_time(-5000), bg=C['bg3'], fg=C['text'], width=8, **_btn_cfg).pack(side=tk.LEFT, padx=6)
        self.btn_play = tk.Button(bg_f, text=self.ICON_PLAY, command=self.toggle_play, width=8, bg=C['accent'], fg='white', **_btn_cfg)
        self.btn_play.pack(side=tk.LEFT, padx=6)
        tk.Button(bg_f, text="5s "+chr(9193), command=lambda: self.skip_time(5000), bg=C['bg3'], fg=C['text'], width=8, **_btn_cfg).pack(side=tk.LEFT, padx=6)

        self.lbl_time = tk.Label(ctrl, text="00:00 / 00:00", bg=C['bg2'], fg=C['text2'], font=('Segoe UI', 9))
        self.lbl_time.pack(side=tk.RIGHT, padx=20)
        
        # --- 자막 렌더링 설정 ---
        sub_f = tk.LabelFrame(left_f, text=" 자막 디자인 ", bg=C['bg2'], fg=C['accent'], padx=10, pady=5, font=('Segoe UI', 10, 'bold'))
        sub_f.pack(fill=tk.X, padx=10, pady=5)
        
        def _pick_c(var, btn, title):
            from tkinter import colorchooser
            c = colorchooser.askcolor(title=title, color=var.get())[1]
            if c:
                var.set(c)
                r, g, b = int(c[1:3],16), int(c[3:5],16), int(c[5:7],16)
                luma = r*0.299 + g*0.587 + b*0.114
                fg_col = "black" if luma > 128 else "white"
                btn.config(bg=c, fg=fg_col, text=f"■ {title}")
            
        r1 = tk.Frame(sub_f, bg=C['bg2']); r1.pack(fill=tk.X, pady=2)
        tk.Label(r1, text="폰트:", bg=C['bg2'], fg=C['text'], font=('Segoe UI', 9)).pack(side=tk.LEFT)
        
        # [ASS 핫스왓] 커스텀 폰트 피커 (시스템 폰트 전체 + 검색 + 자체 프리뷰)
        self._sub_font_name = tk.StringVar(value="맑은 고딕")
        self._font_btn = tk.Button(r1, text="맑은 고딕 ▼", bg=C['bg3'], fg=C['text'], font=("맑은 고딕", 9), relief=tk.FLAT, command=self._open_font_picker, width=14)
        self._font_btn.pack(side=tk.LEFT, padx=(2, 10))
        # sub_font 호환성 래퍼
        class _FontProxy:
            def __init__(self, var): self._var = var
            def get(self): return self._var.get()
            def set(self, v): self._var.set(v)
        self.sub_font = _FontProxy(self._sub_font_name)
        self._sub_font_name.trace_add("write", lambda *_: self._font_btn.config(text=f"{self._sub_font_name.get()} ▼", font=(self._sub_font_name.get(), 9)))
        tk.Label(r1, text="폰트 크기:", bg=C['bg2'], fg=C['text'], font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self.sub_font_size = tk.IntVar(value=80)
        ttk.Combobox(r1, textvariable=self.sub_font_size, values=[50,55,60,65,70,75,80,85,90,95,100,105,110,115,120,125,130,135,140,145,150], width=3, state="readonly").pack(side=tk.LEFT, padx=(2, 10))
        tk.Label(r1, text="자막 상하 위치:", bg=C['bg2'], fg=C['text'], font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self.sub_y_pos = tk.IntVar(value=50)
        tk.Scale(r1, from_=0, to=300, variable=self.sub_y_pos, orient=tk.HORIZONTAL, showvalue=0, bg=C['bg2'], highlightthickness=0, troughcolor=C['bg3'], fg=C['accent'], sliderrelief=tk.FLAT, length=80).pack(side=tk.LEFT)
        
        r2 = tk.Frame(sub_f, bg=C['bg2']); r2.pack(fill=tk.X, pady=4)
        self.sub_color_f = tk.StringVar(value="#ffffff")
        btn_cf = tk.Button(r2, text="■ 글자색", bg="#ffffff", fg="black", font=('Segoe UI', 9), relief=tk.FLAT, command=lambda: _pick_c(self.sub_color_f, btn_cf, "글자색"))
        btn_cf.pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Label(r2, text="윤곽선:", bg=C['bg2'], fg=C['text'], font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self.sub_outline = tk.IntVar(value=3)
        ttk.Combobox(r2, textvariable=self.sub_outline, values=[0,1,2,3,4,5,6,8,10], width=2, state="readonly").pack(side=tk.LEFT, padx=2)
        self.sub_color_o = tk.StringVar(value="#000000")
        btn_co = tk.Button(r2, text="■ 윤곽색", bg="#000000", fg="white", font=('Segoe UI', 9), relief=tk.FLAT, command=lambda: _pick_c(self.sub_color_o, btn_co, "윤곽색"))
        btn_co.pack(side=tk.LEFT, padx=(5, 10))
        
        tk.Label(r2, text="이중윤곽선:", bg=C['bg2'], fg=C['text'], font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self.sub_shadow = tk.IntVar(value=3)
        ttk.Combobox(r2, textvariable=self.sub_shadow, values=[0,1,2,3,4,5,6,8,10], width=2, state="readonly").pack(side=tk.LEFT, padx=2)
        self.sub_color_s = tk.StringVar(value="#000000")
        btn_cs = tk.Button(r2, text="■ 이중윤곽색", bg="#000000", fg="white", font=("bold", 9), relief=tk.FLAT, command=lambda: _pick_c(self.sub_color_s, btn_cs, "이중윤곽색"))
        btn_cs.pack(side=tk.LEFT, padx=5)
        
        # [ASS 핫스왑] 모든 자막 디자인 위젯 변경 시 디바운스로 자동 적용 (CPU 부하 ≈ 0%)
        self._sub_debounce = None
        self._pos_debounce = None
        def _schedule_sub_update(*_):
            if self._sub_debounce: self.root.after_cancel(self._sub_debounce)
            self._sub_debounce = self.root.after(300, self.apply_vlc_sub_settings)
        def _schedule_pos_update(*_):
            if self._pos_debounce: self.root.after_cancel(self._pos_debounce)
            self._pos_debounce = self.root.after(50, self.apply_vlc_sub_settings)
        
        # IntVar / StringVar 트레이스
        self.sub_font_size.trace_add("write", _schedule_sub_update)
        self.sub_y_pos.trace_add("write", _schedule_pos_update)  # 위치는 50ms 디바운스로 실시간 반영
        self.sub_outline.trace_add("write", _schedule_sub_update)
        self.sub_shadow.trace_add("write", _schedule_sub_update)
        self.sub_color_f.trace_add("write", _schedule_sub_update)
        self.sub_color_o.trace_add("write", _schedule_sub_update)
        self.sub_color_s.trace_add("write", _schedule_sub_update)
        # 폰트 이름 변경 트레이스
        self._sub_font_name.trace_add("write", _schedule_sub_update)
        # -----------------------------

        right_f = tk.Frame(self.main_paned, padx=15, bg=C['bg']); self.main_paned.add(right_f, minsize=600, width=800)
        af = tk.LabelFrame(right_f, text=" 분석 및 편집 ", padx=10, pady=10, bg=C['bg2'], fg=C['accent'], font=('Segoe UI', 10, 'bold')); af.pack(fill=tk.X, pady=10)
        tk.Button(af, text="영상 파일 선택", command=self.on_select_video, bg=C['bg3'], fg=C['text'], font=('Segoe UI', 10), relief=tk.FLAT, pady=6).pack(fill=tk.X, pady=5)
        model_f = tk.Frame(af, bg=C['bg2']); model_f.pack(fill=tk.X, pady=5)
        tk.Label(model_f, text="AI 모델:", bg=C['bg2'], fg=C['text'], font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self.ai_model_var = tk.StringVar(value="large-v3-turbo (기본)")
        self.ai_model_combo = ttk.Combobox(model_f, textvariable=self.ai_model_var, values=["large-v3-turbo (기본)", "models/whisper-medium-ko-zeroth (Medium-Zeroth)"], state="readonly", width=60)
        self.ai_model_combo.pack(side=tk.LEFT, padx=5)
        self.ai_model_var.trace_add("write", lambda *args: self.reset_action_button())
        mf = tk.Frame(af, bg=C['bg2']); mf.pack(fill=tk.X)
        self.mode_var = tk.StringVar(value="대사 변환 및 컷편집 (종합)")
        self.mode_combo = ttk.Combobox(mf, textvariable=self.mode_var, values=["자연어-대사 변환", "대사 변환 및 컷편집", "깜놀 구간 탐색", "무음 제거 편집 (VAD)", "자동 챕터 분할 (CLIP)"], state="readonly", width=30)
        self.mode_combo.pack(side=tk.LEFT, padx=5, pady=10); self.mode_var.trace_add("write", lambda *args: self.reset_action_button())
        self.btn_analyze = tk.Button(af, text="분석 시작", command=self.on_start_analysis, bg=C['accent'], fg='white', font=('Segoe UI', 10, 'bold'), relief=tk.FLAT, pady=10); self.btn_analyze.pack(fill=tk.X, pady=5)
        self.btn_stop = tk.Button(af, text="작업 중지", command=self.on_stop_action, bg=C['red'], fg='white', font=('Segoe UI', 10, 'bold'), relief=tk.FLAT, state=tk.DISABLED, pady=6); self.btn_stop.pack(fill=tk.X, pady=2)
        self.save_frame = tk.Frame(right_f, bg=C['bg']); self.save_frame.pack(fill=tk.X, pady=2); self.save_frame.pack_forget()
        tk.Label(self.save_frame, text="영상 및 타임라인 내보내기", fg=C['purple'], bg=C['bg'], font=('Segoe UI', 10, 'bold')).pack(pady=2)
        btn_box = tk.Frame(self.save_frame, bg=C['bg']); btn_box.pack(fill=tk.X, pady=2)
        self.btn_fast_save = tk.Button(btn_box, text="🚀 초고속", command=lambda: self.start_export(fast=True), bg=C['purple'], fg='white', font=('Segoe UI', 9), relief=tk.FLAT, pady=8); self.btn_fast_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.btn_pro_save = tk.Button(btn_box, text="🎯 정밀", command=lambda: self.start_export(fast=False), bg=C['bg3'], fg=C['text'], font=('Segoe UI', 9), relief=tk.FLAT, pady=8); self.btn_pro_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.btn_xml_save = tk.Button(btn_box, text="🎬 XML", command=self.on_export_xml, bg=C['surface'], fg=C['text'], font=('Segoe UI', 9), relief=tk.FLAT, pady=8); self.btn_xml_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.lbl_status = tk.Label(right_f, text="준비됨", fg=C['green'], bg=C['bg'], font=('Segoe UI', 10)); self.lbl_status.pack(fill=tk.X, pady=5)
        self.progress_var = tk.DoubleVar(); ttk.Progressbar(right_f, variable=self.progress_var).pack(fill=tk.X, pady=5)
        list_f = tk.Frame(right_f, bg=C['bg']); list_f.pack(fill=tk.BOTH, expand=True, pady=10)
        
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
        
        # [Ctrl+휠] 자막 시작/종료 시간 ±50ms 미세 조정
        def _on_ctrl_wheel(e):
            if not (e.state & 0x4): return  # Ctrl 키가 눌린 상태가 아니면 무시
            item = self.tree.identify_row(e.y)
            col = self.tree.identify_column(e.x)
            if not item or col not in ('#2', '#3'): return
            
            try:
                idx = int(self.tree.item(item)['values'][0]) - 1
                if idx < 0 or idx >= len(self.results_data): return
                
                delta = 0.05 if e.delta > 0 else -0.05  # ±50ms
                key = 's' if col == '#2' else 'e'
                new_val = max(0, self.results_data[idx][key] + delta)
                
                # 시작이 종료보다 커지지 않도록 안전장치
                if key == 's' and new_val >= self.results_data[idx]['e']: return
                if key == 'e' and new_val <= self.results_data[idx]['s']: return
                
                self.results_data[idx][key] = round(new_val, 3)
                self.tree.set(item, column=col, value=self.format_time(new_val))
                
                # 영상 재생 위치도 조절된 시간으로 이동 (귀로 확인)
                self.player.set_time(int(new_val * 1000))
                
                # ASS 핫스왑으로 자막 실시간 반영
                self.apply_preview_subtitles(force_reload=True)
            except: pass
            return "break"  # 기본 스크롤 동작 차단
        
        self.tree.bind("<MouseWheel>", _on_ctrl_wheel)
        opt = tk.LabelFrame(right_f, text=" 상세 설정 ", padx=10, pady=10, bg=C['bg2'], fg=C['accent'], font=('Segoe UI', 10, 'bold')); opt.pack(fill=tk.X, pady=5)
        
        # [시니어 최적화] UI 공간 절약을 위해 가로 배치 및 간격 조절
        set_f = tk.Frame(opt, bg=C['bg2']); set_f.pack(fill=tk.X, pady=2)
        tk.Label(set_f, text="빔 사이즈:", bg=C['bg2'], fg=C['text'], font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self.beam_size_var = tk.IntVar(value=5)
        tk.Scale(set_f, from_=1, to=15, orient=tk.HORIZONTAL, variable=self.beam_size_var, showvalue=1, length=120, bg=C['bg2'], fg=C['text'], highlightthickness=0, troughcolor=C['bg3'], sliderrelief=tk.FLAT).pack(side=tk.LEFT, padx=5)
        
        chk_f = tk.Frame(opt, bg=C['bg2']); chk_f.pack(fill=tk.X, pady=2)
        self.use_denoise_var = tk.BooleanVar(value=False); tk.Checkbutton(chk_f, text="소음 제거", variable=self.use_denoise_var, bg=C['bg2'], fg=C['text'], selectcolor=C['bg3'], activebackground=C['bg2'], font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self.use_dominant_var = tk.BooleanVar(value=False); tk.Checkbutton(chk_f, text="주인공만", variable=self.use_dominant_var, bg=C['bg2'], fg=C['orange'], selectcolor=C['bg3'], activebackground=C['bg2'], font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=10)
        
        tk.Label(chk_f, text="언어:", bg=C['bg2'], fg=C['text'], font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(10, 0))
        self.lang_var = tk.StringVar(value="한국어 (ko)")
        self.lang_combo = ttk.Combobox(chk_f, textvariable=self.lang_var, values=["한국어 (ko)", "영어 (en)", "일본어 (ja)", "중국어 (zh)", "자동 감지 (auto)"], state="readonly", width=12)
        self.lang_combo.pack(side=tk.LEFT, padx=5)

        vad_f = tk.Frame(opt, bg=C['bg2']); vad_f.pack(fill=tk.X, pady=2)
        
        self.use_silero_vad_var = tk.BooleanVar(value=True)
        tk.Checkbutton(vad_f, text="외부 VAD (Silero)", variable=self.use_silero_vad_var, bg=C['bg2'], fg=C['text'], selectcolor=C['bg3'], activebackground=C['bg2'], font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self.use_whisper_vad_var = tk.BooleanVar(value=True)
        tk.Checkbutton(vad_f, text="내부 VAD (Whisper)", variable=self.use_whisper_vad_var, bg=C['bg2'], fg=C['text'], selectcolor=C['bg3'], activebackground=C['bg2'], font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)

        tk.Label(vad_f, text="무음/패딩:", bg=C['bg2'], fg=C['text'], font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(10, 0))
        self.silence_dur_var = tk.DoubleVar(value=2.0); tk.Entry(vad_f, textvariable=self.silence_dur_var, width=4, bg=C['bg3'], fg=C['text'], insertbackground=C['text'], relief=tk.FLAT).pack(side=tk.LEFT, padx=2)
        tk.Label(vad_f, text="s /", bg=C['bg2'], fg=C['text2'], font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self.speech_pad_var = tk.DoubleVar(value=0.1); tk.Entry(vad_f, textvariable=self.speech_pad_var, width=4, bg=C['bg3'], fg=C['text'], insertbackground=C['text'], relief=tk.FLAT).pack(side=tk.LEFT, padx=2)
        tk.Label(vad_f, text="s", bg=C['bg2'], fg=C['text2'], font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(10, 0))
        self.vad_threshold_var = tk.DoubleVar(value=0.35)
        tk.Scale(vad_f, from_=0.1, to=0.9, resolution=0.05, orient=tk.HORIZONTAL, variable=self.vad_threshold_var, showvalue=1, length=100, bg=C['bg2'], fg=C['text'], highlightthickness=0, troughcolor=C['bg3'], sliderrelief=tk.FLAT).pack(side=tk.LEFT, padx=5)

        adv_f = tk.Frame(opt, bg=C['bg2']); adv_f.pack(fill=tk.X, pady=2)
        
        tk.Label(adv_f, text="가속:", bg=C['bg2'], fg=C['text'], font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self.device_var = tk.StringVar(value="자동 감지 (auto)")
        ttk.Combobox(adv_f, textvariable=self.device_var, values=["자동 감지 (auto)", "NVIDIA (cuda)", "Apple Mac (mps)", "CPU (멀티코어)"], state="readonly", width=14).pack(side=tk.LEFT, padx=5)

        self.remove_punctuation_var = tk.BooleanVar(value=True)
        tk.Checkbutton(adv_f, text="문장 부호 소거 (.,-)", variable=self.remove_punctuation_var, bg=C['bg2'], fg=C['text2'], selectcolor=C['bg3'], activebackground=C['bg2'], font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)

        lf = tk.Frame(opt, bg=C['bg2'])
        lf.pack(fill=tk.X, pady=2)
        
        tk.Label(lf, text="대사 길이:", bg=C['bg2'], fg=C['text'], font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self.max_len_int = tk.IntVar(value=50)
        self.max_len_str = tk.StringVar(value="50")
        
        tk.Scale(lf, from_=10, to=50, orient=tk.HORIZONTAL, variable=self.max_len_int, showvalue=0, command=lambda v: self.max_len_str.set(str(v)), length=150, bg=C['bg2'], fg=C['text'], highlightthickness=0, troughcolor=C['bg3'], sliderrelief=tk.FLAT).pack(side=tk.LEFT, padx=5)
        tk.Entry(lf, textvariable=self.max_len_str, width=3, bg=C['bg3'], fg=C['text'], insertbackground=C['text'], relief=tk.FLAT).pack(side=tk.LEFT)
        
        self.export_format = tk.StringVar(value="SRT")
        tk.Button(lf, text="자막 내보내기", command=self.export_subtitles, bg=C['orange'], fg='white', font=('Segoe UI', 9), relief=tk.FLAT, padx=10).pack(side=tk.RIGHT, padx=5)
        ttk.Combobox(lf, textvariable=self.export_format, values=["SRT", "VTT", "TXT", "CSV"], state="readonly", width=6).pack(side=tk.RIGHT, padx=5)

    def _open_font_picker(self):
        """시스템 폰트 전체를 자체 서체로 미리보기하며 검색/선택하는 팝업"""
        popup = tk.Toplevel(self.root)
        popup.title("폰트 선택")
        popup.geometry("380x500")
        popup.configure(bg="#2d2d2d")
        popup.transient(self.root)
        popup.grab_set()
        
        # 시스템 폰트 목록 (중복 제거 + 정렬)
        all_fonts = sorted(set(tkfont.families()), key=str.lower)
        
        # 검색 입력창
        search_var = tk.StringVar()
        search_entry = tk.Entry(popup, textvariable=search_var, font=("맑은 고딕", 11), bg="#444", fg="white", insertbackground="white")
        search_entry.pack(fill=tk.X, padx=10, pady=(10, 5))
        search_entry.focus_set()
        
        # 폰트 리스트 (Text 위젯 + 스크롤바)
        list_frame = tk.Frame(popup, bg="#2d2d2d")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_w = tk.Text(list_frame, bg="#1a1a1a", fg="white", cursor="hand2", wrap=tk.NONE,
                         yscrollcommand=scrollbar.set, spacing1=2, spacing3=2, padx=8, pady=4)
        text_w.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_w.yview)
        
        def _select_font(fname):
            self._sub_font_name.set(fname)
            popup.destroy()
        
        def _populate(filter_text=""):
            text_w.config(state=tk.NORMAL)
            text_w.delete("1.0", tk.END)
            ft = filter_text.lower()
            for fname in all_fonts:
                if ft and ft not in fname.lower():
                    continue
                tag = f"f_{fname}"
                try:
                    text_w.insert(tk.END, f" {fname}\n", tag)
                    text_w.tag_config(tag, font=(fname, 12), foreground="white")
                    text_w.tag_bind(tag, "<Button-1>", lambda e, f=fname: _select_font(f))
                    text_w.tag_bind(tag, "<Enter>", lambda e, t=tag: text_w.tag_config(t, background="#3a6fd8"))
                    text_w.tag_bind(tag, "<Leave>", lambda e, t=tag: text_w.tag_config(t, background=""))
                except:
                    pass
            text_w.config(state=tk.DISABLED)
        
        _populate()
        
        def _on_search(*_):
            _populate(search_var.get())
        search_var.trace_add("write", _on_search)

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

    def reset_action_button(self): self.save_frame.pack_forget(); self.btn_analyze.config(text="분석 시작", command=self.on_start_analysis, bg=self.C['accent'], state=tk.NORMAL); self.btn_fast_save.config(state=tk.NORMAL); self.btn_pro_save.config(state=tk.NORMAL); self.btn_xml_save.config(state=tk.NORMAL)
    def apply_vlc_sub_settings(self):
        """[ASS 핫스왓] 디자인 변경 시 ASS 파일만 재생성하여 VLC에 즉시 로드"""
        self.apply_preview_subtitles(force_reload=False)

    def on_select_video(self):
        p = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov *.flv")])
        if p:
            self.current_video_path = p
            
            # 기존에 로드된 자막 파일 연결 끊기
            if hasattr(self, 'preview_srt_path'):
                self.preview_srt_path = None
                
            if self.player.load_video(p):
                def _resize():
                    w, h = self.player.get_video_resolution()
                    if w > 0 and h > 0:
                        self._video_aspect = h / w  # 영상 비율 저장
                        cw = self.video_canvas.winfo_width()
                        if cw < 10: cw = 500
                        new_h = int(cw * self._video_aspect)
                        if new_h > 10: self.video_canvas.config(height=new_h)
                    self.video_canvas.pack_propagate(False)
                self.root.after(500, _resize)
                
                self.lbl_status.config(text="영상 로드됨: " + os.path.basename(p), fg=self.C['accent'])
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
            self.lbl_status.config(text="■ 작업 중지 중... 완전 종료 대기", fg=self.C['red'])
            self.btn_stop.config(state=tk.DISABLED)
            self.root.after(1500, lambda: self.reset_action_button() or self.lbl_status.config(text="작업 중지됨", fg=self.C['red']))

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
        """[ASS 핫스왓] 사용자 디자인 설정을 반영한 ASS 파일을 동적 생성하여 VLC에 주입"""
        if not self.results_data or not self.player: return
        try:
            # --- HEX(#RRGGBB) → ASS(&H00BBGGRR&) 변환 ---
            def hex_to_ass(hex_color):
                hex_color = hex_color.lstrip('#')
                r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
                return f"&H00{b:02X}{g:02X}{r:02X}&"
            
            # --- 사용자 UI 설정값 수집 ---
            font_name = getattr(self, 'sub_font', None)
            font_name = font_name.get() if font_name else '맑은 고딕'
            font_size = getattr(self, 'sub_font_size', None)
            font_size = font_size.get() if font_size else 40
            color_f = getattr(self, 'sub_color_f', None)
            color_f = color_f.get() if color_f else '#ffffff'
            outline_w = getattr(self, 'sub_outline', None)
            outline_w = outline_w.get() if outline_w else 3
            color_o = getattr(self, 'sub_color_o', None)
            color_o = color_o.get() if color_o else '#000000'
            shadow_w = getattr(self, 'sub_shadow', None)
            shadow_w = shadow_w.get() if shadow_w else 3
            color_s = getattr(self, 'sub_color_s', None)
            color_s = color_s.get() if color_s else '#000000'
            margin_v = getattr(self, 'sub_y_pos', None)
            margin_v = margin_v.get() if margin_v else 50
            
            ass_primary = hex_to_ass(color_f)
            ass_outline = hex_to_ass(color_o)
            ass_shadow = hex_to_ass(color_s)
            
            # --- ASS 헤더 작성 ---
            ass_header = f"""[Script Info]
Title: VAD AI Studio Preview
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{ass_primary},&H000000FF&,{ass_outline},{ass_shadow},-1,0,0,0,100,100,0,0,1,{outline_w},{shadow_w},2,10,10,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
            # --- ASS 시간 포맷 H:MM:SS.cs ---
            def fmt_ass_time(sec):
                h = int(sec // 3600)
                m = int((sec % 3600) // 60)
                s = int(sec % 60)
                cs = int((sec % 1) * 100)
                return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
            
            lines = []
            for i, r in enumerate(self.results_data):
                s_r, e_r = r['s'], r['e']
                if i < len(self.results_data) - 1 and e_r >= self.results_data[i+1]['s']:
                    e_r = max(s_r + 0.1, self.results_data[i+1]['s'] - 0.05)
                lines.append(f"Dialogue: 0,{fmt_ass_time(s_r)},{fmt_ass_time(e_r)},Default,,0,0,0,,{r['t']}")
            
            # --- A/B 핑퉁 핫스왓 ---
            suffix = "A" if getattr(self, '_ping_pong', False) else "B"
            self._ping_pong = not getattr(self, '_ping_pong', False)
            ass_name = os.path.abspath(f"temp_preview_{suffix}.ass")
            
            with open(ass_name, 'w', encoding='utf-8-sig') as f:
                f.write(ass_header)
                f.write('\n'.join(lines))
                f.write('\n')
            
            self.preview_srt_path = ass_name
            self.player.set_subtitle(ass_name)
            
            # [시니어 최적화] 일시정지 상태일 때 제자리 점프로 프레임 새로고침
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
