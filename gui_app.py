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

class LblMarquee(tk.Canvas):
    def __init__(self, parent, text="", font=('Noto Sans KR', 11), fg='#34C759', bg='#FFFFFF', height=30):
        super().__init__(parent, bg=bg, height=height, highlightthickness=0, bd=0)
        self.fg = fg
        self.font = font
        self.text = text
        self.text1 = self.create_text(0, height//2, text=text, fill=fg, font=font, anchor=tk.W)
        self.text2 = self.create_text(-9999, height//2, text=text, fill=fg, font=font, anchor=tk.W)
        self._running = False
        self.bind("<Configure>", lambda e: self._restart())

    def config(self, text=None, fg=None, **kwargs):
        if text is not None:
            self.text = text
            self.itemconfigure(self.text1, text=text)
            self.itemconfigure(self.text2, text=text)
            self._restart()
        if fg is not None:
            self.fg = fg
            self.itemconfigure(self.text1, fill=fg)
            self.itemconfigure(self.text2, fill=fg)
        if kwargs:
            super().configure(**kwargs)

    def _restart(self):
        self._running = False
        self.after(100, self._start_scroll)

    def _start_scroll(self):
        self._running = True
        self._scroll()

    def _scroll(self):
        if not self._running or not self.winfo_exists(): return
        bbox = self.bbox(self.text1)
        if not bbox: return
        tw = bbox[2] - bbox[0]
        vw = self.winfo_width()
        
        if tw > vw:
            self.move(self.text1, -1, 0)
            self.move(self.text2, -1, 0)
            
            x1 = self.coords(self.text1)[0]
            x2 = self.coords(self.text2)[0]
            
            gap = 60 # 텍스트 사이 간격 (사용자 요청에 따라 짧게 조정)
            
            # 첫 번째 텍스트가 화면 왼쪽으로 완전히 나가면 두 번째 텍스트 뒤로 배치
            if x1 < -tw:
                self.coords(self.text1, x2 + tw + gap, self.winfo_height()//2)
            # 두 번째 텍스트가 화면 왼쪽으로 완전히 나가면 첫 번째 텍스트 뒤로 배치 (또는 초기화 시)
            if x2 < -tw:
                if x1 > vw: # 초기 상태
                    self.coords(self.text2, x1 + tw + gap, self.winfo_height()//2)
                else:
                    self.coords(self.text2, x1 + tw + gap, self.winfo_height()//2)
            
            # 초기 구동 시 두 번째 텍스트 위치 보정
            if x2 < -tw and x1 <= 0:
                 self.coords(self.text2, x1 + tw + gap, self.winfo_height()//2)

        else:
            self.coords(self.text1, (vw-tw)//2, self.winfo_height()//2)
            self.coords(self.text2, -9999, -9999)
            
        self.after(30, self._scroll)

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
        self.root.configure(bg='#F2F2F7')
        
        # [Apple HIG] 라이트 모드 색상 팔레트
        self.C = {
            'bg':       '#F2F2F7',  # System Grouped Background
            'bg2':      '#FFFFFF',  # Card / Elevated
            'bg3':      '#E1E1E6',  # Control Fill (연한 회색)
            'surface':  '#E5E5EA',  # Surface / Separator
            'border':   '#E5E5E7',  # Border
            'text':     '#1D1D1F',  # Primary Label
            'text2':    '#86868B',  # Secondary Label
            'accent':   '#007AFF',  # System Blue
            'green':    '#34C759',  # System Green
            'red':      '#FF3B30',  # System Red
            'orange':   '#FF9500',  # System Orange
            'purple':   '#AF52DE',  # System Purple
            'teal':     '#5AC8FA',  # System Teal
        }
        C = self.C
        
        # [Apple HIG] ttk 스타일 테마
        style = ttk.Style()
        style.theme_use('clam')
        _font = ('Noto Sans KR', 10); _font_s = ('Noto Sans KR', 11); _font_h = ('Noto Sans KR', 11, 'bold')
        style.configure('.', background=C['bg'], foreground=C['text'], font=_font, borderwidth=0)
        style.configure('TFrame', background=C['bg'])
        style.configure('TLabel', background=C['bg'], foreground=C['text'], font=_font)
        style.configure('TLabelframe', background=C['bg2'], foreground=C['text'])
        style.configure('TLabelframe.Label', background=C['bg2'], foreground=C['accent'], font=_font_h)
        # Treeview rowheight를 34px로 조정 (11pt 폰트 대응)
        # 선택된 행의 색상을 투명한 느낌의 연파랑으로 조정
        style.map('Treeview', background=[('selected', '#E7F1FF')], foreground=[('selected', C['text'])])
        style.map('Treeview.Heading', background=[('active', C['bg3'])])
        
        # [사용자 요청] Treeview에 수직 구분선 느낌 추가
        style.configure('Treeview', borderwidth=1, relief='flat', background=C['bg2'], fieldbackground=C['bg2'])
        # 행 높이 및 글꼴 설정 복구 (이전 에딧에서 누락된 부분 보강)
        style.configure('Treeview', rowheight=34, font=_font_s)
        style.configure('Treeview.Heading', background=C['bg2'], foreground=C['text2'], font=('Noto Sans KR', 10), borderwidth=0, relief='flat')
        
        style.layout('Treeview.Item', [('Treeview.padding', {'sticky': 'nswe', 'children': [('Treeview.indicator', {'side': 'left', 'sticky': ''}), ('Treeview.image', {'side': 'left', 'sticky': ''}), ('Treeview.text', {'sticky': 'nswe'})]})])
        style.configure('TNotebook', background=C['bg'], borderwidth=0)
        style.configure('TNotebook.Tab', background=C['bg3'], foreground=C['text2'],
                         font=_font_s, padding=[14, 7], borderwidth=0)
        style.map('TNotebook.Tab', background=[('selected', C['accent'])], foreground=[('selected', '#ffffff')])
        # 컴보박스 아래만 연한 선이 있는 Minimalist 느낌
        style.configure('TCombobox', fieldbackground=C['bg2'], background=C['bg2'],
                         foreground=C['text'], arrowcolor=C['text2'], borderwidth=0, lightcolor=C['border'], darkcolor=C['bg'], bordercolor=C['bg2'], relief='flat')
        style.map('TCombobox', fieldbackground=[('readonly', C['bg2'])], foreground=[('readonly', C['text'])])
        style.configure('Horizontal.TProgressbar', troughcolor=C['bg3'], background=C['accent'],
                         borderwidth=0, thickness=4)
        style.configure('TScrollbar', background=C['bg3'], troughcolor=C['bg2'], borderwidth=0, arrowcolor=C['text2'])
        
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
        if hasattr(self, 'block_editor'):
            self.block_editor.render_block_view()
        
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
        _f = ('Noto Sans KR', 11); _fb = ('Noto Sans KR', 11, 'bold')
        def _hover(btn, n, h):
            btn.bind('<Enter>', lambda e: btn.config(bg=h))
            btn.bind('<Leave>', lambda e: btn.config(bg=n))
        
        # ── 최상위: 좌측(비디오+타임라인) | 우측(인스펙터) ──
        self.main_paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.FLAT, sashwidth=6, bg=C['border'])
        self.main_paned.pack(fill=tk.BOTH, expand=True)
        
        center_frame = tk.Frame(self.main_paned, bg=C['bg'])
        self.main_paned.add(center_frame, minsize=600, width=900)
        
        # 세로 분할: 상단(비디오) | 하단(타임라인)
        self.v_paned = tk.PanedWindow(center_frame, orient=tk.VERTICAL, sashrelief=tk.FLAT, sashwidth=6, bg=C['border'])
        self.v_paned.pack(fill=tk.BOTH, expand=True)
        v_paned = self.v_paned
        
        video_zone = tk.Frame(v_paned, bg='#000000')
        v_paned.add(video_zone, minsize=200, height=480)

        self._video_aspect = 9 / 16
        self.video_canvas = tk.Frame(video_zone, bg='black')
        self.video_canvas.pack(fill=tk.BOTH, expand=True)
        self.video_canvas.bind('<Button-1>', lambda e: self.toggle_play())
        
        # [시니어 최적화] 패널 폭 변경 시 영상 비율 유지하며 높이를 동적으로 재계산
        def _on_canvas_resize(e):
            new_w = e.width
            if new_w > 10:
                new_h = int(new_w * self._video_aspect)
                if new_h > 10 and abs(new_h - self.video_canvas.winfo_height()) > 5:
                    self.video_canvas.config(height=new_h)
        self.video_canvas.bind("<Configure>", _on_canvas_resize)

        self.seek_var = tk.DoubleVar()
        self.seek_bar = tk.Scale(video_zone, from_=0, to=1000, orient=tk.HORIZONTAL, variable=self.seek_var, showvalue=0, bg=C['bg2'], highlightthickness=0, troughcolor=C['bg3'], fg=C['accent'], sliderrelief=tk.FLAT, sliderlength=12)
        self.seek_bar.pack(fill=tk.X, padx=12, pady=(0, 2), side=tk.BOTTOM)
        self.seek_bar.bind('<ButtonPress-1>', self.on_seek_start)
        self.seek_bar.bind('<ButtonRelease-1>', self.on_seek_release)
        self.seek_bar.bind('<B1-Motion>', self.on_seek_motion)

        ctrl = tk.Frame(video_zone, bg=C['bg2'], pady=6)
        ctrl.pack(fill=tk.X, side=tk.BOTTOM)
        
        bg_f = tk.Frame(ctrl, bg=C['bg2'])
        bg_f.pack(expand=True)
        
        _bc = dict(font=_f, relief='flat', bd=0, compound='center', padx=10, pady=3, cursor='hand2')
        b1 = tk.Button(bg_f, text='  ' + chr(9194)+' 5s  ', command=lambda: self.skip_time(-5000), bg=C['bg3'], fg=C['text'], width=8, **_bc); b1.pack(side=tk.LEFT, padx=4); _hover(b1, C['bg3'], C['border'])
        self.btn_play = tk.Button(bg_f, text='  ' + self.ICON_PLAY + '  ', command=self.toggle_play, width=8, bg=C['accent'], fg='white', **_bc)
        self.btn_play.pack(side=tk.LEFT, padx=4); _hover(self.btn_play, C['accent'], '#0062CC')
        b2 = tk.Button(bg_f, text='  5s '+chr(9193) + '  ', command=lambda: self.skip_time(5000), bg=C['bg3'], fg=C['text'], width=8, **_bc); b2.pack(side=tk.LEFT, padx=4); _hover(b2, C['bg3'], C['border'])

        self.lbl_time = tk.Label(ctrl, text='00:00 / 00:00', bg=C['bg2'], fg=C['text2'], font=_f)
        self.lbl_time.pack(side=tk.RIGHT, padx=16)
        
        # [사용자 요청] 자막 스타일 설정은 '⚙️ 자막 설정' 탭으로 완전 이관됨 (하단 코드 참고)

        # ═══ ZONE 2: 타임라인 (Bottom) ═══
        timeline_zone = tk.Frame(v_paned, bg=C['bg'])
        v_paned.add(timeline_zone, minsize=120, height=220)
        
        self.notebook = ttk.Notebook(timeline_zone)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.tab_tree = tk.Frame(self.notebook, bg=C['bg2'])
        self.notebook.add(self.tab_tree, text=' 📋 자막 리스트 ')
        
        self.tab_canvas = tk.Frame(self.notebook, bg=C['bg'])
        self.notebook.add(self.tab_canvas, text=' 🧩 단어 블록 ')
        
        # [사용자 요청] 자막 설정 탭 별도 분리
        self.tab_style = tk.Frame(self.notebook, bg=C['bg'])
        self.notebook.add(self.tab_style, text=' ⚙️ 자막 설정 ')
        
        # ── 자막 리스트 Treeview 설정 ──
        self.tree = ttk.Treeview(self.tab_tree, columns=('no','start','end','text'), show='headings')
        self.tree.tag_configure('active', background='#D0E5FF')
        self.tree.heading('no', text='#'); self.tree.heading('start', text='시작'); self.tree.heading('end', text='종료'); self.tree.heading('text', text='내용')
        self.tree.column('no', width=34, anchor=tk.CENTER); self.tree.column('start', width=70, anchor=tk.CENTER); self.tree.column('end', width=70, anchor=tk.CENTER); self.tree.column('text', width=400)
        sc = ttk.Scrollbar(self.tab_tree, orient=tk.VERTICAL, command=self.tree.yview); self.tree.configure(yscrollcommand=sc.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sc.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.block_editor = UIBlockEditor(self.tab_canvas, self.root, self.transcript_manager, lambda: self.player, self.rebuild_tree_and_render)
        def _on_tab_changed(e):
            idx = self.notebook.index(self.notebook.select())
            if idx == 1:
                self.block_editor.render_block_view()
                self.block_editor.block_canvas.yview_moveto(self.tree.yview()[0])
            elif idx == 0:
                self.tree.yview_moveto(self.block_editor.block_canvas.yview()[0])
        self.notebook.bind('<<NotebookTabChanged>>', _on_tab_changed)
        
        # ═══ ZONE 3: 인스펙터 패널 (Right) ═══
        inspector = tk.Frame(self.main_paned, bg=C['bg'])
        self.main_paned.add(inspector, minsize=280, width=320)
        
        insp_scroll = tk.Canvas(inspector, bg=C['bg'], highlightthickness=0, bd=0)
        insp_sb = ttk.Scrollbar(inspector, orient=tk.VERTICAL, command=insp_scroll.yview)
        insp_inner = tk.Frame(insp_scroll, bg=C['bg'])
        insp_inner.bind('<Configure>', lambda e: insp_scroll.configure(scrollregion=insp_scroll.bbox('all')))
        insp_scroll.create_window((0,0), window=insp_inner, anchor='nw', tags='inner')
        insp_scroll.bind('<Configure>', lambda e: insp_scroll.itemconfig('inner', width=e.width))
        insp_scroll.configure(yscrollcommand=insp_sb.set)
        insp_sb.pack(side=tk.RIGHT, fill=tk.Y); insp_scroll.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inspector.bind('<Enter>', lambda e: insp_scroll.bind_all('<MouseWheel>', lambda ev: insp_scroll.yview_scroll(int(-1*(ev.delta/120)), 'units')))
        inspector.bind('<Leave>', lambda e: insp_scroll.unbind_all('<MouseWheel>'))
        
        # 카드 유틸 (그림자는 하단에 1px 두께 라벨 추가 꼼수로 구현)
        def _card(parent, title=''):
            f = tk.Frame(parent, bg=C['bg2'], highlightbackground=C['border'], highlightthickness=1, bd=0, padx=16, pady=12); f.pack(fill=tk.X, padx=12, pady=(0, 2))
            shadow = tk.Frame(parent, bg='#E5E5E7', height=2); shadow.pack(fill=tk.X, padx=14, pady=(0, 6)); shadow.pack_propagate(False) # 그림자
            if title: tk.Label(f, text=title, bg=C['bg2'], fg=C['text'], font=('Noto Sans KR', 11, 'bold')).pack(anchor=tk.W, pady=(0, 6))
            return f
        def _row(parent):
            r = tk.Frame(parent, bg=C['bg2']); r.pack(fill=tk.X, pady=4); return r
        def _sep(parent):
            tk.Frame(parent, bg=C['border'], height=1).pack(fill=tk.X, pady=8)
        
        
        # ── 카드 1: 소스 및 엔진 ──
        c1 = _card(insp_inner, '🎬  소스 및 엔진')
        bf = tk.Button(c1, text='  📂  영상 파일 선택  ', command=self.on_select_video, bg=C['bg3'], fg=C['text'], font=_f, relief='flat', bd=0, compound='center', pady=8, cursor='hand2'); bf.pack(fill=tk.X, pady=(0,6)); _hover(bf, C['bg3'], C['border'])
        r = _row(c1); tk.Label(r, text='AI 모델', bg=C['bg2'], fg=C['text2'], font=_f).pack(side=tk.LEFT)
        self.ai_model_var = tk.StringVar(value='large-v3-turbo (기본)')
        self.ai_model_combo = ttk.Combobox(r, textvariable=self.ai_model_var, values=['large-v3-turbo (기본)', 'models/whisper-medium-ko-zeroth (Medium-Zeroth)'], state='readonly', width=24); self.ai_model_combo.pack(side=tk.RIGHT)
        self.ai_model_var.trace_add('write', lambda *_: self.reset_action_button())
        _sep(c1)
        r = _row(c1); tk.Label(r, text='가속 장치', bg=C['bg2'], fg=C['text2'], font=_f).pack(side=tk.LEFT)
        self.device_var = tk.StringVar(value='자동 감지 (auto)'); ttk.Combobox(r, textvariable=self.device_var, values=['자동 감지 (auto)', 'NVIDIA (cuda)', 'Apple Mac (mps)', 'CPU (멀티코어)'], state='readonly', width=14).pack(side=tk.RIGHT)
        r = _row(c1); tk.Label(r, text='언어', bg=C['bg2'], fg=C['text2'], font=_f).pack(side=tk.LEFT)
        self.lang_var = tk.StringVar(value='한국어 (ko)'); self.lang_combo = ttk.Combobox(r, textvariable=self.lang_var, values=['한국어 (ko)', '영어 (en)', '일본어 (ja)', '중국어 (zh)', '자동 감지 (auto)'], state='readonly', width=12); self.lang_combo.pack(side=tk.RIGHT)
        
        # ── 카드 2: 분석 모드 ──
        c2 = _card(insp_inner, '⚡  분석 모드')
        self.mode_var = tk.StringVar(value='대사 변환 및 컷편집 (종합)')
        self.mode_combo = ttk.Combobox(c2, textvariable=self.mode_var, values=['자연어-대사 변환', '대사 변환 및 컷편집', '깜놀 구간 탐색', '무음 제거 편집 (VAD)', '자동 챕터 분할 (CLIP)'], state='readonly')
        self.mode_combo.pack(fill=tk.X, pady=(0,6)); self.mode_var.trace_add('write', lambda *_: self.reset_action_button())
        self.btn_analyze = tk.Button(c2, text='  분석 시작  ', command=self.on_start_analysis, bg=C['accent'], fg='white', font=('Noto Sans KR', 13, 'bold'), relief='flat', bd=0, compound='center', pady=10, cursor='hand2'); self.btn_analyze.pack(fill=tk.X, pady=(0,4)); _hover(self.btn_analyze, C['accent'], '#0062CC')
        self.btn_stop = tk.Button(c2, text='  작업 중지  ', command=self.on_stop_action, bg=C['bg3'], fg=C['red'], font=_fb, relief='flat', bd=0, compound='center', state=tk.DISABLED, pady=5, cursor='hand2'); self.btn_stop.pack(fill=tk.X); _hover(self.btn_stop, C['bg3'], C['border'])
        self.lbl_status = LblMarquee(c2, text='준비됨', fg=C['green'], bg=C['bg2'], font=_f); self.lbl_status.pack(fill=tk.X, pady=(6,0))
        self.progress_var = tk.DoubleVar(); ttk.Progressbar(c2, variable=self.progress_var).pack(fill=tk.X, pady=(4,0))
        self.save_frame = tk.Frame(c2, bg=C['bg2']); self.save_frame.pack(fill=tk.X, pady=4); self.save_frame.pack_forget()
        btn_box = tk.Frame(self.save_frame, bg=C['bg2']); btn_box.pack(fill=tk.X)
        self.btn_fast_save = tk.Button(btn_box, text='  🚀 초고속  ', command=lambda: self.start_export(fast=True), bg=C['purple'], fg='white', font=_f, relief='flat', bd=0, compound='center', pady=6, cursor='hand2'); self.btn_fast_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,2)); _hover(self.btn_fast_save, C['purple'], '#9342B5')
        self.btn_pro_save = tk.Button(btn_box, text='  🎯 정밀  ', command=lambda: self.start_export(fast=False), bg=C['bg3'], fg=C['text'], font=_f, relief='flat', bd=0, compound='center', pady=6, cursor='hand2'); self.btn_pro_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2); _hover(self.btn_pro_save, C['bg3'], C['border'])
        self.btn_xml_save = tk.Button(btn_box, text='  🎬 XML  ', command=self.on_export_xml, bg=C['bg3'], fg=C['text'], font=_f, relief='flat', bd=0, compound='center', pady=6, cursor='hand2'); self.btn_xml_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2,0)); _hover(self.btn_xml_save, C['bg3'], C['border'])
        
        # ── 카드 3: 세부 튜닝 (다시 밖으로 이동) ──
        c3 = _card(insp_inner, '🎛  세부 튜닝')
        
        # [내부 고정 값] 빔 사이즈 5, 소음 제거/주인공 기능 UI 제거 (사용자 요청)
        self.beam_size_var = tk.IntVar(value=5)
        self.use_denoise_var = tk.BooleanVar(value=False)
        self.use_dominant_var = tk.BooleanVar(value=False)
        
        chk_cfg = dict(bg=C['bg2'], selectcolor=C['bg3'], activebackground=C['bg2'], font=_f, relief=tk.FLAT, bd=0)
        self.remove_punctuation_var = tk.BooleanVar(value=True); tk.Checkbutton(c3, text='✂️문장부호 제거', variable=self.remove_punctuation_var, fg=C['text2'], **chk_cfg).pack(anchor=tk.W, pady=1)
        _sep(c3)
        self.use_silero_vad_var = tk.BooleanVar(value=True); tk.Checkbutton(c3, text='외부 VAD (Silero)', variable=self.use_silero_vad_var, fg=C['text'], **chk_cfg).pack(anchor=tk.W, pady=1)
        self.use_whisper_vad_var = tk.BooleanVar(value=True); tk.Checkbutton(c3, text='내부 VAD (Whisper)', variable=self.use_whisper_vad_var, fg=C['text'], **chk_cfg).pack(anchor=tk.W, pady=1)
        _sep(c3)
        
        r = _row(c3); tk.Label(r, text='무음 길이', bg=C['bg2'], fg=C['text2'], font=_f).pack(side=tk.LEFT)
        self.silence_dur_var = tk.DoubleVar(value=2.0); tk.Entry(r, textvariable=self.silence_dur_var, width=5, bg=C['bg3'], fg=C['text'], insertbackground=C['text'], relief=tk.FLAT, font=_f).pack(side=tk.RIGHT)
        
        r = _row(c3); tk.Label(r, text='음성 패딩', bg=C['bg2'], fg=C['text2'], font=_f).pack(side=tk.LEFT)
        self.speech_pad_var = tk.DoubleVar(value=0.1); tk.Entry(r, textvariable=self.speech_pad_var, width=5, bg=C['bg3'], fg=C['text'], insertbackground=C['text'], relief=tk.FLAT, font=_f).pack(side=tk.RIGHT)
        
        r = _row(c3); tk.Label(r, text='VAD 임계', bg=C['bg2'], fg=C['text2'], font=_f).pack(side=tk.LEFT)
        self.vad_threshold_var = tk.DoubleVar(value=0.35); tk.Scale(r, from_=0.1, to=0.9, resolution=0.05, orient=tk.HORIZONTAL, variable=self.vad_threshold_var, showvalue=1, length=120, bg=C['bg2'], highlightthickness=0, troughcolor=C['bg3'], sliderrelief=tk.FLAT).pack(side=tk.RIGHT)
        
        r = _row(c3); tk.Label(r, text='대사 길이', bg=C['bg2'], fg=C['text2'], font=_f).pack(side=tk.LEFT)
        self.max_len_int = tk.IntVar(value=50)
        tk.Scale(r, from_=10, to=80, orient=tk.HORIZONTAL, variable=self.max_len_int, showvalue=1, length=120, bg=C['bg2'], highlightthickness=0, troughcolor=C['bg3'], sliderrelief=tk.FLAT).pack(side=tk.RIGHT)
        
        # [사용자 요청] ── 자막 설정 (스타일) 탭 UI 통합 구현 ──
        cs = self.tab_style
        st_inner = tk.Frame(cs, bg=C['bg'], padx=30, pady=20); st_inner.pack(fill=tk.BOTH, expand=True)
        
        def _st_row(label):
            fr = tk.Frame(st_inner, bg=C['bg']); fr.pack(fill=tk.X, pady=8)
            tk.Label(fr, text=label, bg=C['bg'], fg=C['text'], font=_fb, width=14, anchor=tk.W).pack(side=tk.LEFT)
            return fr

        # 디바운스 타이머 및 실시간 업데이트
        self._sub_debounce = None
        def _update_sub(*_):
            if self._sub_debounce: self.root.after_cancel(self._sub_debounce)
            self._sub_debounce = self.root.after(200, lambda: self.apply_preview_subtitles(force_reload=True))

        # --- 폰트 이름 (커스텀 피커 연동) ---
        self._sub_font_name = tk.StringVar(value='맑은 고딕')
        class _FontProxy:
            def __init__(self, var): self._var = var
            def get(self): return self._var.get()
            def set(self, v): self._var.set(v)
        self.sub_font = _FontProxy(self._sub_font_name)
        
        r = _st_row('🔤 폰트 이름')
        self._font_btn = tk.Button(r, text='맑은 고딕 ▼', bg=C['bg3'], fg=C['text'], font=('맑은 고딕', 10), relief=tk.FLAT, command=self._open_font_picker, width=20, cursor='hand2')
        self._font_btn.pack(side=tk.LEFT)
        self._sub_font_name.trace_add('write', lambda *_: [self._font_btn.config(text=f"{self._sub_font_name.get()} ▼", font=(self._sub_font_name.get(), 10)), _update_sub()])

        # --- 폰트 크기 ---
        self.sub_font_size = tk.IntVar(value=80)
        r = _st_row('📏 폰트 크기')
        tk.Scale(r, from_=10, to=200, orient=tk.HORIZONTAL, variable=self.sub_font_size, length=280, bg=C['bg'], highlightthickness=0, troughcolor=C['bg3'], sliderrelief=tk.FLAT).pack(side=tk.LEFT)
        self.sub_font_size.trace_add('write', _update_sub)

        # --- 글자 색상 ---
        self.sub_color_f = tk.StringVar(value='#FFFFFF')
        r = _st_row('🎨 글자 색상')
        def _pick_f():
            c = tk.colorchooser.askcolor(initialcolor=self.sub_color_f.get())[1]
            if c: self.sub_color_f.set(c); _update_sub()
        tk.Button(r, text=' 색상 선택 ', command=_pick_f, bg=C['bg3'], fg=C['text'], relief='flat', padx=12, pady=2, font=_f, cursor='hand2').pack(side=tk.LEFT)
        tk.Label(r, textvariable=self.sub_color_f, bg=C['bg'], fg=C['text2'], font=_f).pack(side=tk.LEFT, padx=15)

        # --- 테두리 두께 ---
        self.sub_outline = tk.IntVar(value=3)
        r = _st_row('〰️ 테두리 두께')
        tk.Scale(r, from_=0, to=15, orient=tk.HORIZONTAL, variable=self.sub_outline, length=280, bg=C['bg'], highlightthickness=0, troughcolor=C['bg3'], sliderrelief=tk.FLAT).pack(side=tk.LEFT)
        self.sub_outline.trace_add('write', _update_sub)

        # --- 테두리 색상 ---
        self.sub_color_o = tk.StringVar(value='#000000')
        r = _st_row('🎨 테두리 색상')
        def _pick_o():
            c = tk.colorchooser.askcolor(initialcolor=self.sub_color_o.get())[1]
            if c: self.sub_color_o.set(c); _update_sub()
        tk.Button(r, text=' 색상 선택 ', command=_pick_o, bg=C['bg3'], fg=C['text'], relief='flat', padx=12, pady=2, font=_f, cursor='hand2').pack(side=tk.LEFT)
        tk.Label(r, textvariable=self.sub_color_o, bg=C['bg'], fg=C['text2'], font=_f).pack(side=tk.LEFT, padx=15)

        # --- 그림자 깊이 ---
        self.sub_shadow = tk.IntVar(value=3)
        r = _st_row('👥 그림자 깊이')
        tk.Scale(r, from_=0, to=15, orient=tk.HORIZONTAL, variable=self.sub_shadow, length=280, bg=C['bg'], highlightthickness=0, troughcolor=C['bg3'], sliderrelief=tk.FLAT).pack(side=tk.LEFT)
        self.sub_shadow.trace_add('write', _update_sub)

        # --- 그림자 색상 ---
        self.sub_color_s = tk.StringVar(value='#000000')
        r = _st_row('🎨 그림자 색상')
        def _pick_s():
            c = tk.colorchooser.askcolor(initialcolor=self.sub_color_s.get())[1]
            if c: self.sub_color_s.set(c); _update_sub()
        tk.Button(r, text=' 색상 선택 ', command=_pick_s, bg=C['bg3'], fg=C['text'], relief='flat', padx=12, pady=2, font=_f, cursor='hand2').pack(side=tk.LEFT)
        tk.Label(r, textvariable=self.sub_color_s, bg=C['bg'], fg=C['text2'], font=_f).pack(side=tk.LEFT, padx=15)

        # --- 자막 위치(Y) ---
        self.sub_y_pos = tk.IntVar(value=50)
        r = _st_row('📍 자막 위치(Y)')
        tk.Scale(r, from_=0, to=400, orient=tk.HORIZONTAL, variable=self.sub_y_pos, length=280, bg=C['bg'], highlightthickness=0, troughcolor=C['bg3'], sliderrelief=tk.FLAT).pack(side=tk.LEFT)
        self.sub_y_pos.trace_add('write', _update_sub)

        # ── 카드 4: 내보내기 ──
        c4 = _card(insp_inner, '📤  내보내기')
        r = _row(c4); tk.Label(r, text='포맷', bg=C['bg2'], fg=C['text2'], font=_f).pack(side=tk.LEFT)
        self.export_format = tk.StringVar(value='SRT'); ttk.Combobox(r, textvariable=self.export_format, values=['SRT', 'VTT', 'TXT', 'CSV'], state='readonly', width=8).pack(side=tk.RIGHT)
        bx = tk.Button(c4, text='  📄 자막 내보내기  ', command=self.export_subtitles, bg=C['orange'], fg='white', font=_fb, relief='flat', bd=0, compound='center', pady=8, cursor='hand2'); bx.pack(fill=tk.X, pady=(8,0)); _hover(bx, C['orange'], '#E08600')
        
        # [Apple HIG] 컨텍스트 메뉴 및 이벤트 바인딩
        self.menu = tk.Menu(self.root, tearoff=0, bg=C['bg2'], fg=C['text'], activebackground=C['accent'], activeforeground='white', font=_f)
        self.menu.add_command(label='📍 시작 지점으로 이동', command=self.jump_to_start)
        self.menu.add_command(label='📍 종료 지점으로 이동', command=self.jump_to_end)
        self.menu.add_separator()
        self.menu.add_command(label='📝 대사 수정', command=self.edit_selected_text)
        
        self.tree.bind('<ButtonRelease-1>', self.on_tree_click)
        self.tree.bind('<Button-3>', self.show_context_menu)

        # [Apple HIG] PanedWindow 핸들 시각화 (Vrew 스타일)
        self._add_sash_handle(self.main_paned, 'h')
        self._add_sash_handle(self.v_paned, 'v')

        # [Ctrl+휠] 자막 시작/종료 시간 ±50ms 미세 조정 (Apple HIG)
        def _on_ctrl_wheel(e):
            if not (e.state & 0x4): return # Ctrl 안 눌림 -> 기본 스크롤 허용
            
            # [사용자 요청] Ctrl 눌린 경우, 시간 조절 가능 영역이 아니더라도 스크롤 차단
            item = self.tree.identify_row(e.y)
            col = self.tree.identify_column(e.x)
            if item and col in ('#2', '#3'):
                try:
                    idx = int(self.tree.item(item)['values'][0]) - 1
                    if 0 <= idx < len(self.results_data):
                        # 휠 방향 반전: 위로(delta>0) 올리면 시간 감소(-), 아래로(delta<0) 내리면 시간 증가(+)
                        delta = -0.05 if e.delta > 0 else 0.05
                        key = 's' if col == '#2' else 'e'
                        nv = max(0, self.results_data[idx][key] + delta)
                        
                        # 안전장치 및 차단 로직
                        valid = True
                        if key == 's':
                            if nv >= self.results_data[idx]['e'] or (idx > 0 and nv < self.results_data[idx-1]['e']): valid = False
                        else: # key == 'e'
                            if nv <= self.results_data[idx]['s'] or (idx < len(self.results_data)-1 and nv > self.results_data[idx+1]['s']): valid = False
                        
                        if valid:
                            self.results_data[idx][key] = round(nv, 3)
                            self.tree.set(item, column=col, value=self.format_time(nv))
                            self.player.set_time(int(nv * 1000))
                            self.player.play()
                            self.apply_preview_subtitles(force_reload=True)
                except Exception as e: print(f'[WARN] Ctrl+휠 시간 조절 오류: {e}')
            return 'break' # Ctrl 눌린 상태에선 조절 성공 여부와 무관하게 스크롤 방지
        self.tree.bind('<MouseWheel>', _on_ctrl_wheel)


        






    def _open_font_picker(self):
        """시스템 폰트 전체를 자체 서체로 미리보기하며 검색/선택하는 팝업"""
        popup = tk.Toplevel(self.root)
        popup.title("폰트 선택")
        popup.geometry("380x500")
        popup.configure(bg=self.C['bg'])
        popup.transient(self.root)
        popup.grab_set()
        
        # 시스템 폰트 목록 (중복 제거 + 정렬)
        all_fonts = sorted(set(tkfont.families()), key=str.lower)
        
        # 검색 입력창
        search_var = tk.StringVar()
        search_entry = tk.Entry(popup, textvariable=search_var, font=('Noto Sans KR', 11), bg=self.C['bg2'], fg=self.C['text'], insertbackground=self.C['text'], relief=tk.FLAT)
        search_entry.pack(fill=tk.X, padx=14, pady=(14, 8))
        search_entry.focus_set()
        
        # 폰트 리스트 (Text 위젯 + 스크롤바)
        list_frame = tk.Frame(popup, bg=self.C['bg'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 14))
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_w = tk.Text(list_frame, bg=self.C['bg2'], fg=self.C['text'], cursor='hand2', wrap=tk.NONE,
                         yscrollcommand=scrollbar.set, spacing1=4, spacing3=4, padx=10, pady=6, bd=0)
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
                    text_w.tag_config(tag, font=(fname, 12), foreground=self.C['text'])
                    text_w.tag_bind(tag, "<Button-1>", lambda e, f=fname: _select_font(f))
                    text_w.tag_bind(tag, "<Enter>", lambda e, t=tag: text_w.tag_config(t, background=self.C['bg3']))
                    text_w.tag_bind(tag, "<Leave>", lambda e, t=tag: text_w.tag_config(t, background=""))
                except:
                    pass
            text_w.config(state=tk.DISABLED)
        
        _populate()
        
        def _on_search(*_):
            _populate(search_var.get())
        search_var.trace_add("write", _on_search)

    def bind_keys(self):
        def _is_editing():
            """현재 포커스가 텍스트 편집 위젯에 있으면 True (키 이벤트 차단)"""
            w = self.root.focus_get()
            return isinstance(w, (tk.Entry, tk.Text))

        def _on_space(e):
            if _is_editing(): return  # 편집 중엔 스페이스바를 위젯에 넘김
            self.toggle_play()
            return "break"

        def _on_left(e):
            if _is_editing(): return  # 편집 중엔 좌방향키를 위젯에 넘김
            self.skip_time(-5000)
            return "break"

        def _on_right(e):
            if _is_editing(): return  # 편집 중엔 우방향키를 위젯에 넘김
            self.skip_time(5000)
            return "break"

        self.root.bind_all("<space>", _on_space)
        self.root.bind_all("<Left>",  _on_left)
        self.root.bind_all("<Right>", _on_right)

        # [사용자 요청] 탭이나 리스트에 포커스가 있을 때 방향키로 메뉴가 넘어가는 Tkinter 기본 동작 차단
        try:
            self.root.unbind_class('TNotebook', '<Left>')
            self.root.unbind_class('TNotebook', '<Right>')
            self.root.unbind_class('Treeview', '<Left>')
            self.root.unbind_class('Treeview', '<Right>')
        except: pass
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

    def reset_action_button(self): self.save_frame.pack_forget(); self.btn_analyze.config(text="  분석 시작  ", command=self.on_start_analysis, bg=self.C['accent'], state=tk.NORMAL); self.btn_fast_save.config(state=tk.NORMAL); self.btn_pro_save.config(state=tk.NORMAL); self.btn_xml_save.config(state=tk.NORMAL)
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
                except Exception as e: print(f'[WARN] 트리 클릭 시간 이동 오류: {e}')
            
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
            except Exception as e: print(f'[WARN] 인라인 편집 저장 오류: {e}')

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
ScaledBorderAndShadow: yes

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
            _script_dir = os.path.dirname(os.path.abspath(__file__))
            ass_name = os.path.join(_script_dir, f"temp_preview_{suffix}.ass")
            
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
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f'[ERROR] apply_preview_subtitles 실패: {e}')
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
        except Exception as e: print(f'[WARN] 시크바 이동 오류: {e}')


    def update_loop(self):
        if self.player:
            if not self.is_seeking:
                pos = self.player.get_position()
                if pos >= 0: self.seek_var.set(pos * 1000)
            curr_ms = self.player.get_time()
            total_ms = self.player.get_length()
            
            if curr_ms >= 0 and total_ms > 0:
                c_m, c_s = divmod(int(curr_ms/1000), 60); t_m, t_s = divmod(int(total_ms/1000), 60); self.lbl_time.config(text=f"{c_m:02d}:{c_s:02d} / {t_m:02d}:{t_s:02d}")
                
                # [사용자 요청] 현재 재생 중인 자막 찾기 및 강조
                curr_sec = curr_ms / 1000.0
                active_idx = -1
                for i, r in enumerate(self.results_data):
                    if r['s'] <= curr_sec <= r['e']:
                        active_idx = i
                        break
                
                if hasattr(self, '_last_active_idx') and self._last_active_idx != active_idx:
                    current_tab = self.notebook.index(self.notebook.select())
                    
                    # Treeview 강조
                    for item in self.tree.get_children():
                        val = self.tree.item(item)['values']
                        if val and int(val[0]) - 1 == active_idx:
                            self.tree.item(item, tags=('active',))
                            if current_tab == 0: self.tree.see(item) # 자막 리스트 탭일 때만 스크롤
                        else:
                            self.tree.item(item, tags=())
                    
                    # 단어 블록 강조 (스크롤은 내부 메서드에서 탭 확인 후 수행)
                    self.block_editor.set_active_row(active_idx, follow= (current_tab == 1))
                    self._last_active_idx = active_idx
                elif not hasattr(self, '_last_active_idx'):
                    self._last_active_idx = -2 # 초기화

            if hasattr(self, 'btn_play'): self.btn_play.config(text=self.ICON_PAUSE if self.player.is_playing() else self.ICON_PLAY)
        
        # 실시간성 향상을 위해 100ms 주기로 변경
        self.root.after(100, self.update_loop)
    def _add_sash_handle(self, paned, orient='h'):
        """PanedWindow의 Sash 위치에 마우스 호버 시 반응하는 시각적 핸들(Pill)을 추가"""
        C = self.C
        # 핸들 프레임 생성 (Pill 모양 모사)
        if orient == 'h':
            handle = tk.Frame(paned, bg=C['border'], width=4, height=40, cursor="sb_h_double_arrow")
        else:
            handle = tk.Frame(paned, bg=C['border'], width=40, height=4, cursor="sb_v_double_arrow")
        
        def _on_enter(e): handle.config(bg=C['accent'])
        def _on_leave(e): handle.config(bg=C['border'])
        handle.bind("<Enter>", _on_enter)
        handle.bind("<Leave>", _on_leave)
        
        # 드래그 중에도 핸들이 Sash를 따라다니도록 실시간 추적
        def _sync_position():
            try:
                if not paned.winfo_exists(): return
                # PanedWindow에 위젯이 2개 이상 추가되어 Sash가 생성된 경우에만 작동
                # [오류 수정] tk.PanedWindow에는 count() 메서드가 없으므로 panes()의 길이로 체크
                if len(paned.panes()) > 1:
                    coords = paned.sash_coord(0)
                    if orient == 'h':
                        # 수직 핸들을 Sash 중앙에 배치
                        ph = paned.winfo_height()
                        handle.place(x=coords[0] + 1, y=(ph - 40) // 2)
                    else:
                        # 수평 핸들을 Sash 중앙에 배치
                        pw = paned.winfo_width()
                        handle.place(x=(pw - 40) // 2, y=coords[1] + 1)
                self.root.after(100, _sync_position)
            except Exception as e: print(f'[WARN] Sash 핸들 동기화 오류: {e}')
        
        _sync_position()

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
