import os
import sys
import threading
import time
import math
import queue
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk, font as tkfont
import numpy as np
import vlc
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageOps
from engine_core import HyperTranscriptionEngine, HAS_WHISPERX
from video_editor import VideoEditor
from app.services.video_player import VideoPlayer
from app.models.config_models import AnalysisSettings
from app.models.timeline_manager import TranscriptManager
from app.utils.event_dispatcher import EventEmitter
from analysis_controller import AnalysisController
from ui_block_editor import UIBlockEditor
from app.models.overlay_manager import OverlayManager
from app.adapters.subtitle_overlay_adapter import build_subtitle_overlays

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
            
            gap = 60 # ??용뮞??????揶쏄쑨爰?(??????遺욧퍕???怨뺤뵬 筌욁룓苡?鈺곌퀣??
            
            # 筌?甕곕뜆????용뮞?硫? ?遺얇늺 ??긱걹??곗쨮 ?袁⑹읈?????筌???甕곕뜆????용뮞????살쨮 獄쏄퀣??
            if x1 < -tw:
                self.coords(self.text1, x2 + tw + gap, self.winfo_height()//2)
            # ??甕곕뜆????용뮞?硫? ?遺얇늺 ??긱걹??곗쨮 ?袁⑹읈?????筌?筌?甕곕뜆????용뮞????살쨮 獄쏄퀣??(?癒?뮉 ?λ뜃由????
            if x2 < -tw:
                if x1 > vw: # ?λ뜃由??怨밴묶
                    self.coords(self.text2, x1 + tw + gap, self.winfo_height()//2)
                else:
                    self.coords(self.text2, x1 + tw + gap, self.winfo_height()//2)
            
            # 珥덇린 援щ룞 ????踰덉㎏ ?띿뒪???꾩튂 蹂댁젙
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

    def _report_startup_progress(self, percent, message):
        cb = getattr(self, '_startup_progress_cb', None)
        if cb is None:
            return
        try:
            cb(percent, message)
        except Exception:
            pass
    def __init__(self, root, startup_progress=None):
        self.root = root
        self._startup_progress_cb = startup_progress
        self._report_startup_progress(10, "Applying theme...")
        ctk.set_appearance_mode('light')
        ctk.set_default_color_theme('blue')
        self.root.title("VAD AI Studio v26")
        self.root.geometry("1300x850")
        self.root.configure(bg='#F2F2F7')
        
        # [Apple HIG] ?쇱씠??紐⑤뱶 ?됱긽 ?붾젅??
        self.C = {
            'bg':       '#F2F2F7',  # System Grouped Background
            'bg2':      '#FFFFFF',  # Card / Elevated
            'bg3':      '#E1E1E6',  # Control Fill (?고븳 ?뚯깋)
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
        
        # [Apple HIG] ttk ?ㅽ????뚮쭏
        style = ttk.Style()
        style.theme_use('clam')
        _font = ('Noto Sans KR', 10); _font_s = ('Noto Sans KR', 11); _font_h = ('Noto Sans KR', 11, 'bold')
        style.configure('.', background=C['bg'], foreground=C['text'], font=_font, borderwidth=0)
        style.configure('TFrame', background=C['bg'])
        style.configure('TLabel', background=C['bg'], foreground=C['text'], font=_font)
        style.configure('TLabelframe', background=C['bg2'], foreground=C['text'])
        style.configure('TLabelframe.Label', background=C['bg2'], foreground=C['accent'], font=_font_h)
        # Treeview rowheight瑜?34px濡?議곗젙 (11pt ?고듃 ???
        # ?좏깮???됱쓽 ?됱긽???щ챸???먮굦???고뙆?묒쑝濡?議곗젙
        style.map('Treeview', background=[('selected', '#E7F1FF')], foreground=[('selected', C['text'])])
        style.map('Treeview.Heading', background=[('active', C['bg3'])])
        
        # [?ъ슜???붿껌] Treeview???섏쭅 援щ텇???먮굦 異붽?
        style.configure('Treeview', borderwidth=1, relief='flat', background=C['bg2'], fieldbackground=C['bg2'])
        # ???믪씠 諛?湲瑗??ㅼ젙 蹂듦뎄 (?댁쟾 ?먮뵩?먯꽌 ?꾨씫??遺遺?蹂닿컯)
        style.configure('Treeview', rowheight=34, font=_font_s)
        style.configure('Treeview.Heading', background=C['bg2'], foreground=C['text2'], font=('Noto Sans KR', 10), borderwidth=0, relief='flat')
        
        style.layout('Treeview.Item', [('Treeview.padding', {'sticky': 'nswe', 'children': [('Treeview.indicator', {'side': 'left', 'sticky': ''}), ('Treeview.image', {'side': 'left', 'sticky': ''}), ('Treeview.text', {'sticky': 'nswe'})]})])
        style.configure('TNotebook', background=C['bg'], borderwidth=0)
        style.configure('TNotebook.Tab', background=C['bg3'], foreground=C['text2'],
                         font=_font_s, padding=[14, 7], borderwidth=0)
        style.map('TNotebook.Tab', background=[('selected', C['accent'])], foreground=[('selected', '#ffffff')])
        # 而대낫諛뺤뒪 ?꾨옒留??고븳 ?좎씠 ?덈뒗 Minimalist ?먮굦
        style.configure('TCombobox', fieldbackground=C['bg2'], background=C['bg2'],
                         foreground=C['text'], arrowcolor=C['text2'], borderwidth=0, lightcolor=C['border'], darkcolor=C['bg'], bordercolor=C['bg2'], relief='flat')
        style.map('TCombobox', fieldbackground=[('readonly', C['bg2'])], foreground=[('readonly', C['text'])])
        style.configure('Horizontal.TProgressbar', troughcolor=C['bg3'], background=C['accent'],
                         borderwidth=0, thickness=4)
        style.configure('TScrollbar', background=C['bg3'], troughcolor=C['bg2'], borderwidth=0, arrowcolor=C['text2'])
        self._report_startup_progress(30, "Preparing engines...")
        
        self.engine = HyperTranscriptionEngine()
        self.video_editor = VideoEditor()
        self.player = None
        self.stop_event = threading.Event()
        self._is_closing = False
        self.transcript_manager = TranscriptManager()
        self.current_video_path = None
        self.is_seeking = False
        self.ICON_PLAY = chr(9654); self.ICON_PAUSE = chr(9208)
        self.dispatcher = EventEmitter()
        self._ui_queue = queue.Queue()
        # [?쒕땲?? ?깆쓽 ?ㅽ뻾 寃쎈줈 ?뺣? 異붿쟻 (System32 ???됰슧??CWD 諛⑹뼱)
        self.base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        self.controller = AnalysisController(self.engine, self.video_editor, self.transcript_manager, self.dispatcher)
        self.overlay_manager = OverlayManager()
        self.subtitle_adapter_overrides = {}
        self._timeline_fps = 30.0
        self._overlay_photo_refs = {}
        self._overlay_drag = {"item_id": None, "mode": None, "start_x": 0, "start_y": 0, "origin": None}
        self._overlay_preview_cache = {}
        self._overlay_source_image_cache = {}
        self._overlay_preview_source_cache = {}
        self._overlay_label_refs = {}
        self._overlay_canvas_refs = {}
        self._overlay_resize_refresh_job = None
        self._overlay_prop_refresh_job = None
        self._overlay_resize_dirty_item = None
        self._overlay_last_visible_signature = None
        self.overlay_prop_vars = {
            'text': tk.StringVar(value=''),
            'x': tk.StringVar(value=''),
            'y': tk.StringVar(value=''),
            'width': tk.StringVar(value=''),
            'height': tk.StringVar(value=''),
            'start_time': tk.StringVar(value=''),
            'end_time': tk.StringVar(value=''),
            'opacity': tk.StringVar(value=''),
            'font_size': tk.StringVar(value=''),
            'text_color': tk.StringVar(value=''),
            'rotation': tk.StringVar(value=''),
            'visible': tk.BooleanVar(value=True),
        }
        self.overlay_prop_entries = {}
        self._report_startup_progress(50, "Building interface...")
        self.setup_ui()
        self._report_startup_progress(75, "Connecting player...")
        self.player = VideoPlayer(self.video_canvas.winfo_id())
        self.bind_keys()
        self.bind_events()
        self.root.after(16, self._drain_ui_queue)
        self._report_startup_progress(90, "Finalizing startup...")
        self.load_engine_async()
        self.update_loop()
        
        # [?쒕땲?? ?꾨줈洹몃옩 醫낅즺 ??李뚭볼湲??뚯씪 泥?냼 ?꾨줈?좎퐳 ?깅줉
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self._report_startup_progress(100, '준비 완료')

    def on_closing(self):
        """Clean up temp files and stop background work before exit."""
        self._is_closing = True
        self.stop_event.set()
        try:
            import glob
            import shutil
            # 1. Remove temporary ASS subtitle files.
            for f in glob.glob(os.path.join(self.base_dir, "export_burn_*.ass")):
                try:
                    os.remove(f)
                except OSError:
                    pass

            # 2. Remove temporary working folders.
            for d in glob.glob(os.path.join(self.base_dir, "temp_fast_*")):
                try:
                    shutil.rmtree(d, ignore_errors=True)
                except OSError:
                    pass

            if self.player:
                self.player.stop()
        except Exception:
            pass
        finally:
            try:
                if self.root.winfo_exists():
                    self.root.destroy()
            except tk.TclError:
                pass

    def _queue_ui(self, callback):
        if self._is_closing:
            return
        self._ui_queue.put(callback)

    def _run_ui_callback(self, callback):
        if self._is_closing:
            return
        try:
            if not self.root.winfo_exists():
                return
            callback()
        except tk.TclError:
            pass
        except RuntimeError:
            pass

    def _drain_ui_queue(self):
        if self._is_closing:
            return
        try:
            while True:
                callback = self._ui_queue.get_nowait()
                self._run_ui_callback(callback)
        except queue.Empty:
            pass
        except tk.TclError:
            return
        if not self._is_closing:
            self.root.after(16, self._drain_ui_queue)

    def bind_events(self):
        self.dispatcher.on("progress", lambda x: self._queue_ui(lambda: self._on_progress(x)))
        self.dispatcher.on("add_row", lambda x: self._queue_ui(lambda: self._on_add_row(x)))
        self.dispatcher.on("complete", lambda x: self._queue_ui(lambda: self._on_complete(x)))
        self.dispatcher.on("message", lambda x: self._queue_ui(lambda: messagebox.showinfo('완료', x["text"])))
        self.dispatcher.on("error", lambda x: self._queue_ui(lambda: messagebox.showerror('오류', x["text"])))
        self.dispatcher.on("ghost_defense", lambda x: self._queue_ui(lambda: [self.reset_action_button(), self.btn_stop.configure(state=tk.DISABLED)]))

    def _on_progress(self, task):
        self.progress_var.set(task["value"]); self.lbl_status.config(text=task["text"])
        
    def _on_add_row(self, task):
        self.tree.insert("", "end", values=(task["i"], self.format_time(task['s']), self.format_time(task['e']), task['t']))
        if hasattr(self, 'block_editor'):
            self.block_editor.render_block_view()
            
        # [?ъ슜???붿껌] 遺꾩꽍 以??앹꽦?섎뒗 ?먮쭑???곸긽???ㅼ떆媛꾩쑝濡??낇옒 (?붾컮?댁뒪濡?遺???쒖뼱)
        if getattr(self, '_add_row_debounce', None):
            self.root.after_cancel(self._add_row_debounce)
        self._add_row_debounce = self.root.after(500, lambda: self.apply_preview_subtitles(force_reload=False))
        
    def _on_complete(self, task):
        self.lbl_status.config(text=task["text"], fg=self.C['green'])
        self.progress_var.set(100)
        self.btn_analyze.configure(state=tk.NORMAL)
        has_results = bool(self.results_data)
        if task.get("is_vad") or task.get("is_whisper") or has_results:
            self.save_frame.pack(fill=tk.X, pady=5, before=self.lbl_status)
            for b in [self.btn_fast_save, self.btn_pro_save]:
                b.configure(state=tk.NORMAL)

        if task.get("is_whisper"):
            self.apply_preview_subtitles()
        self.btn_stop.configure(state=tk.DISABLED)

    def setup_ui(self):
        C = self.C
        _f = ('Noto Sans KR', 11); _fb = ('Noto Sans KR', 11, 'bold')
        def _hover(btn, n, h):
            btn.bind('<Enter>', lambda e: btn.config(bg=h))
            btn.bind('<Leave>', lambda e: btn.config(bg=n))
        
        # ?? 理쒖긽?? 醫뚯륫(鍮꾨뵒????꾨씪?? | ?곗륫(?몄뒪?숉꽣) ??
        self.main_paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.FLAT, sashwidth=6, bg=C['border'])
        self.main_paned.pack(fill=tk.BOTH, expand=True)
        
        center_frame = tk.Frame(self.main_paned, bg=C['bg'])
        self.main_paned.add(center_frame, minsize=600, width=900)
        
        # ?몃줈 遺꾪븷: ?곷떒(鍮꾨뵒?? | ?섎떒(??꾨씪??
        self.v_paned = tk.PanedWindow(center_frame, orient=tk.VERTICAL, sashrelief=tk.FLAT, sashwidth=6, bg=C['border'])
        self.v_paned.pack(fill=tk.BOTH, expand=True)
        v_paned = self.v_paned
        
        video_zone = tk.Frame(v_paned, bg='#000000')
        v_paned.add(video_zone, minsize=200, height=480)

        self._video_aspect = 9 / 16
        self.video_frame = tk.Frame(video_zone, bg='black')
        self.video_frame.pack(fill=tk.BOTH, expand=True)
        self.video_canvas = tk.Frame(self.video_frame, bg='black')
        self.video_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self._overlay_transparent_key = '#00FE00'
        self.preview_overlay_window = tk.Toplevel(self.root)
        self.preview_overlay_window.withdraw()
        self.preview_overlay_window.overrideredirect(True)
        try:
            self.preview_overlay_window.attributes('-transparentcolor', self._overlay_transparent_key)
        except tk.TclError:
            pass
        try:
            self.preview_overlay_window.attributes('-topmost', True)
        except tk.TclError:
            pass
        self.preview_overlay_window.configure(bg=self._overlay_transparent_key)
        self.preview_overlay_canvas = tk.Canvas(self.preview_overlay_window, bg=self._overlay_transparent_key, highlightthickness=0, bd=0)
        self.preview_overlay_canvas.pack(fill=tk.BOTH, expand=True)
        self.preview_overlay_canvas.bind('<Button-1>', self.on_overlay_press)
        self.preview_overlay_canvas.bind('<B1-Motion>', self.on_overlay_drag)
        self.preview_overlay_canvas.bind('<ButtonRelease-1>', self.on_overlay_release)
        self.overlay_resize_handle = tk.Frame(self.preview_overlay_window, width=10, height=10, bg='#007AFF', cursor='bottom_right_corner')
        self.overlay_resize_handle.place_forget()
        self.overlay_resize_handle.bind('<Button-1>', self.on_overlay_handle_press)
        self.overlay_resize_handle.bind('<B1-Motion>', self.on_overlay_drag)
        self.overlay_resize_handle.bind('<ButtonRelease-1>', self.on_overlay_release)
        self.overlay_rotate_handle = tk.Frame(self.preview_overlay_window, width=12, height=12, bg='#FF9F0A', cursor='exchange')
        self.overlay_rotate_handle.place_forget()
        self.overlay_rotate_handle.bind('<Button-1>', self.on_overlay_rotate_press)
        self.overlay_rotate_handle.bind('<B1-Motion>', self.on_overlay_drag)
        self.overlay_rotate_handle.bind('<ButtonRelease-1>', self.on_overlay_release)
        self.video_frame.bind('<Button-1>', lambda e: self.toggle_play())
        def _on_canvas_resize(e):
            self.refresh_overlay_preview()
        self.video_frame.bind("<Configure>", _on_canvas_resize)

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
        b1 = tk.Button(bg_f, text='뒤로 5초', command=lambda: self.skip_time(-5000), bg=C['bg3'], fg=C['text'], width=8, **_bc); b1.pack(side=tk.LEFT, padx=4); _hover(b1, C['bg3'], C['border'])
        self.btn_play = tk.Button(bg_f, text='재생', command=self.toggle_play, width=8, bg=C['accent'], fg='white', **_bc)
        self.btn_play.pack(side=tk.LEFT, padx=4); _hover(self.btn_play, C['accent'], '#0062CC')
        b2 = tk.Button(bg_f, text='앞으로 5초', command=lambda: self.skip_time(5000), bg=C['bg3'], fg=C['text'], width=8, **_bc); b2.pack(side=tk.LEFT, padx=4); _hover(b2, C['bg3'], C['border'])

        self.lbl_time = tk.Label(ctrl, text='00:00 / 00:00', bg=C['bg2'], fg=C['text2'], font=_f)
        self.lbl_time.pack(side=tk.RIGHT, padx=16)
        
        # [?ъ슜???붿껌] ?먮쭑 ?ㅽ????ㅼ젙? '?숋툘 ?먮쭑 ?ㅼ젙' ??쑝濡??꾩쟾 ?닿???(?섎떒 肄붾뱶 李멸퀬)

        # ?먥븧??ZONE 2: ??꾨씪??(Bottom) ?먥븧??
        timeline_zone = tk.Frame(v_paned, bg=C['bg'])
        v_paned.add(timeline_zone, minsize=120, height=220)
        
        self.notebook = ttk.Notebook(timeline_zone)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.tab_canvas = tk.Frame(self.notebook, bg=C['bg'])
        self.notebook.add(self.tab_canvas, text=' 단어 블록 ')
        self.tab_overlay = tk.Frame(self.notebook, bg=C['bg'])
        self.notebook.add(self.tab_overlay, text=' 오버레이 타임라인 ')
        
        self.tab_tree = tk.Frame(self.notebook, bg=C['bg2'])
        self.notebook.add(self.tab_tree, text=' 자막 리스트 ')
        
        # [?ъ슜???붿껌] ?먮쭑 ?ㅼ젙 ??蹂꾨룄 遺꾨━
        self.tab_style = tk.Frame(self.notebook, bg=C['bg'])
        self.notebook.add(self.tab_style, text=' 자막 설정 ')
        self.notebook.select(self.tab_canvas)
        
        # ?? ?먮쭑 由ъ뒪??Treeview ?ㅼ젙 ??
        self.tree = ttk.Treeview(self.tab_tree, columns=('no','start','end','text'), show='headings')
        self.tree.tag_configure('active', background='#D0E5FF')
        self.tree.heading('no', text='#'); self.tree.heading('start', text='시작'); self.tree.heading('end', text='종료'); self.tree.heading('text', text='대사')
        self.tree.column('no', width=34, anchor=tk.CENTER); self.tree.column('start', width=70, anchor=tk.CENTER); self.tree.column('end', width=70, anchor=tk.CENTER); self.tree.column('text', width=400)
        sc = ttk.Scrollbar(self.tab_tree, orient=tk.VERTICAL, command=self.tree.yview); self.tree.configure(yscrollcommand=sc.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sc.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.block_editor = UIBlockEditor(self.tab_canvas, self.root, self.transcript_manager, lambda: self.player, self.rebuild_tree_and_render)
        def _on_tab_changed(e):
            idx = self.notebook.index(self.notebook.select())
            if idx == 0: # ?⑥뼱 釉붾줉
                self.block_editor.render_block_view()
                self.block_editor.block_canvas.yview_moveto(self.tree.yview()[0])
            elif idx == 1: # ?먮쭑 由ъ뒪??
                self.tree.yview_moveto(self.block_editor.block_canvas.yview()[0])
        self.notebook.bind('<<NotebookTabChanged>>', _on_tab_changed)
        overlay_toolbar = tk.Frame(self.tab_overlay, bg=C['bg'])
        overlay_toolbar.pack(fill=tk.X, padx=8, pady=(8, 4))
        self.btn_add_image_overlay = tk.Button(overlay_toolbar, text='이미지 오버레이 추가', command=self.add_image_overlay, bg=C['bg2'], fg=C['text'], relief='flat', bd=0, padx=10, pady=6, cursor='hand2')
        self.btn_add_image_overlay.pack(side=tk.LEFT)
        self.btn_add_text_overlay = tk.Button(overlay_toolbar, text='텍스트 오버레이 추가', command=self.add_text_overlay, bg=C['bg2'], fg=C['text'], relief='flat', bd=0, padx=10, pady=6, cursor='hand2')
        self.btn_add_text_overlay.pack(side=tk.LEFT, padx=(6, 0))
        self.use_subtitle_adapter_var = tk.BooleanVar(value=False)
        self.subtitle_adapter_check = tk.Checkbutton(overlay_toolbar, text='자막 어댑터', variable=self.use_subtitle_adapter_var, command=lambda: (self.refresh_overlay_preview(), self.refresh_overlay_timeline()), bg=C['bg'], fg=C['text'], selectcolor=C['bg3'], activebackground=C['bg'], activeforeground=C['text'], relief='flat', bd=0, highlightthickness=0, font=_f)
        self.subtitle_adapter_check.pack(side=tk.LEFT, padx=(8, 0))
        tk.Label(overlay_toolbar, text='배율', bg=C['bg'], fg=C['text2'], font=_f).pack(side=tk.LEFT, padx=(12, 4))
        self.overlay_zoom_var = tk.StringVar(value='1x')
        self.overlay_zoom_combo = ttk.Combobox(overlay_toolbar, textvariable=self.overlay_zoom_var, state='readonly', width=6, values=('1x', '2x', '4x', '8x'))
        self.overlay_zoom_combo.pack(side=tk.LEFT)
        self.overlay_zoom_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_overlay_timeline())
        tk.Label(overlay_toolbar, text='스냅', bg=C['bg'], fg=C['text2'], font=_f).pack(side=tk.LEFT, padx=(12, 4))
        self.overlay_snap_var = tk.StringVar(value='0.1초')
        self.overlay_snap_combo = ttk.Combobox(overlay_toolbar, textvariable=self.overlay_snap_var, state='readonly', width=12, values=('끄기', '0.1초', '프레임'))
        self.overlay_snap_combo.pack(side=tk.LEFT)

        overlay_body = tk.Frame(self.tab_overlay, bg=C['bg'])
        overlay_body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        overlay_timeline_wrap = tk.Frame(overlay_body, bg=C['bg'])
        overlay_timeline_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.overlay_timeline_canvas = tk.Canvas(overlay_timeline_wrap, bg=C['bg2'], highlightthickness=0)
        self.overlay_timeline_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.overlay_timeline_hscroll = ttk.Scrollbar(overlay_timeline_wrap, orient=tk.HORIZONTAL, command=self.overlay_timeline_canvas.xview)
        self.overlay_timeline_hscroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.overlay_timeline_canvas.configure(xscrollcommand=self.overlay_timeline_hscroll.set)
        self.overlay_timeline_canvas.bind('<Button-1>', self.on_overlay_timeline_press)
        self.overlay_timeline_canvas.bind('<B1-Motion>', self.on_overlay_timeline_drag)
        self.overlay_timeline_canvas.bind('<ButtonRelease-1>', self.on_overlay_timeline_release)
        self._overlay_timeline_playhead = None
        self._overlay_timeline_cycle = {'key': None, 'index': 0, 'items': []}

        overlay_props_outer = tk.Frame(overlay_body, bg=C['bg2'], width=250)
        overlay_props_outer.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        overlay_props_outer.pack_propagate(False)
        self.overlay_props_canvas = tk.Canvas(overlay_props_outer, bg=C['bg2'], highlightthickness=0, bd=0)
        self.overlay_props_scroll = ttk.Scrollbar(overlay_props_outer, orient=tk.VERTICAL, command=self.overlay_props_canvas.yview)
        self.overlay_props_inner = tk.Frame(self.overlay_props_canvas, bg=C['bg2'])
        self.overlay_props_inner.bind('<Configure>', lambda e: self.overlay_props_canvas.configure(scrollregion=self.overlay_props_canvas.bbox('all')))
        self._overlay_props_window = self.overlay_props_canvas.create_window((0, 0), window=self.overlay_props_inner, anchor='nw')
        self.overlay_props_canvas.bind('<Configure>', lambda e: self.overlay_props_canvas.itemconfigure(self._overlay_props_window, width=e.width))
        self.overlay_props_canvas.configure(yscrollcommand=self.overlay_props_scroll.set)
        self.overlay_props_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.overlay_props_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        overlay_props = self.overlay_props_inner
        tk.Label(overlay_props, text='오버레이 속성', bg=C['bg2'], fg=C['text'], font=('Noto Sans KR', 10, 'bold')).pack(anchor='w', padx=12, pady=(12, 8))

        def _overlay_prop_row(parent, key, label_text):
            row = tk.Frame(parent, bg=C['bg2'])
            row.pack(fill=tk.X, padx=12, pady=3)
            tk.Label(row, text=label_text, bg=C['bg2'], fg=C['text2'], width=9, anchor='w', font=_f).pack(side=tk.LEFT)
            ent = tk.Entry(row, textvariable=self.overlay_prop_vars[key], bg=C['bg3'], fg=C['text'], relief='flat', bd=4, insertbackground=C['text'])
            ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)
            self.overlay_prop_entries[key] = ent

        _overlay_prop_row(overlay_props, 'text', '텍스트')
        _overlay_prop_row(overlay_props, 'x', 'X 위치')
        _overlay_prop_row(overlay_props, 'y', 'Y 위치')
        _overlay_prop_row(overlay_props, 'width', '너비')
        _overlay_prop_row(overlay_props, 'height', '높이')
        _overlay_prop_row(overlay_props, 'start_time', '시작 시간')
        _overlay_prop_row(overlay_props, 'end_time', '종료 시간')
        _overlay_prop_row(overlay_props, 'opacity', '불투명도')
        _overlay_prop_row(overlay_props, 'font_size', '글자 크기')
        _overlay_prop_row(overlay_props, 'text_color', '글자색')
        _overlay_prop_row(overlay_props, 'rotation', '회전')

        self.overlay_visible_check = tk.Checkbutton(overlay_props, text='표시', variable=self.overlay_prop_vars['visible'], command=self.on_toggle_selected_overlay_visible, bg=C['bg2'], fg=C['text'], selectcolor=C['bg3'], activebackground=C['bg2'], activeforeground=C['text'], relief='flat', bd=0, highlightthickness=0, font=_f)
        self.overlay_visible_check.pack(anchor='w', padx=12, pady=(6, 4))

        layer_btn_row1 = tk.Frame(overlay_props, bg=C['bg2'])
        layer_btn_row1.pack(fill=tk.X, padx=12, pady=(4, 3))
        self.btn_overlay_forward = tk.Button(layer_btn_row1, text='한 단계 앞으로', command=lambda: self.reorder_selected_overlay('forward'), bg=C['bg3'], fg=C['text'], relief='flat', bd=0, padx=8, pady=6, cursor='hand2')
        self.btn_overlay_forward.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        self.btn_overlay_backward = tk.Button(layer_btn_row1, text='한 단계 뒤로', command=lambda: self.reorder_selected_overlay('backward'), bg=C['bg3'], fg=C['text'], relief='flat', bd=0, padx=8, pady=6, cursor='hand2')
        self.btn_overlay_backward.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))

        layer_btn_row2 = tk.Frame(overlay_props, bg=C['bg2'])
        layer_btn_row2.pack(fill=tk.X, padx=12, pady=(0, 6))
        self.btn_overlay_front = tk.Button(layer_btn_row2, text='맨 앞으로', command=lambda: self.reorder_selected_overlay('front'), bg=C['bg3'], fg=C['text'], relief='flat', bd=0, padx=8, pady=6, cursor='hand2')
        self.btn_overlay_front.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        self.btn_overlay_back = tk.Button(layer_btn_row2, text='맨 뒤로', command=lambda: self.reorder_selected_overlay('back'), bg=C['bg3'], fg=C['text'], relief='flat', bd=0, padx=8, pady=6, cursor='hand2')
        self.btn_overlay_back.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))

        self.btn_apply_overlay_props = tk.Button(overlay_props, text='속성 적용', command=self.apply_selected_overlay_properties, bg=C['accent'], fg='white', relief='flat', bd=0, padx=10, pady=6, cursor='hand2')
        self.btn_apply_overlay_props.pack(fill=tk.X, padx=12, pady=(6, 6))
        self.btn_delete_overlay = tk.Button(overlay_props, text='선택 오버레이 삭제', command=self.delete_selected_overlay, bg=C['red'], fg='white', relief='flat', bd=0, padx=10, pady=6, cursor='hand2')
        self.btn_delete_overlay.pack(fill=tk.X, padx=12, pady=(0, 6))
        self.lbl_overlay_props = tk.Label(overlay_props, text='선택된 오버레이가 없습니다', bg=C['bg2'], fg=C['text2'], anchor='w', justify=tk.LEFT, font=_f)
        self.lbl_overlay_props.pack(fill=tk.X, padx=12, pady=(0, 12))
        self.root.bind_all('<MouseWheel>', self._on_overlay_props_mousewheel, add='+')
        self.root.bind_all('<Button-4>', self._on_overlay_props_mousewheel, add='+')
        self.root.bind_all('<Button-5>', self._on_overlay_props_mousewheel, add='+')
        self.refresh_overlay_property_panel()
        
        # ?먥븧??ZONE 3: ?몄뒪?숉꽣 ?⑤꼸 (Right) ?먥븧??
        inspector = tk.Frame(self.main_paned, bg=C['bg'])
        self.main_paned.add(inspector, minsize=280, width=340)

        insp_scroll = tk.Canvas(inspector, bg=C['bg'], highlightthickness=0, bd=0)
        insp_sb = ttk.Scrollbar(inspector, orient=tk.VERTICAL, command=insp_scroll.yview)
        insp_inner = tk.Frame(insp_scroll, bg=C['bg'])
        insp_inner.bind('<Configure>', lambda e: insp_scroll.configure(scrollregion=insp_scroll.bbox('all')))
        insp_scroll.create_window((0, 0), window=insp_inner, anchor='nw', tags='inner')
        insp_scroll.bind('<Configure>', lambda e: insp_scroll.itemconfig('inner', width=e.width))
        insp_scroll.configure(yscrollcommand=insp_sb.set)
        insp_sb.pack(side=tk.RIGHT, fill=tk.Y)
        insp_scroll.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inspector.bind('<Enter>', lambda e: insp_scroll.bind_all('<MouseWheel>', lambda ev: insp_scroll.yview_scroll(int(-1 * (ev.delta / 120)), 'units')))
        inspector.bind('<Leave>', lambda e: insp_scroll.unbind_all('<MouseWheel>'))

        def _ctk_button(parent, text, command, kind='secondary', height=38, width=None):
            palette = {
                'primary': dict(fg_color=C['accent'], hover_color='#0062CC', text_color='#FFFFFF'),
                'secondary': dict(fg_color=C['bg3'], hover_color=C['border'], text_color=C['text']),
                'danger': dict(fg_color='#FFF1F0', hover_color='#FFE5E2', text_color=C['red']),
                'purple': dict(fg_color=C['purple'], hover_color='#9342B5', text_color='#FFFFFF'),
                'orange': dict(fg_color=C['orange'], hover_color='#E08600', text_color='#FFFFFF'),
            }
            kwargs = dict(text=text, command=command, height=height, corner_radius=14, border_width=0, font=_f, **palette[kind])
            if width is not None:
                kwargs['width'] = width
            return ctk.CTkButton(parent, **kwargs)

        def _card(parent, title=''):
            shell = tk.Frame(parent, bg=C['bg'])
            shell.pack(fill=tk.X, padx=12, pady=(0, 6))
            card = ctk.CTkFrame(shell, fg_color=C['bg2'], corner_radius=18, border_width=1, border_color=C['border'])
            card.pack(fill=tk.X)
            if title:
                ctk.CTkLabel(card, text=title, text_color=C['text'], font=('Noto Sans KR', 12, 'bold')).pack(anchor=tk.W, padx=16, pady=(14, 8))
            return card

        def _row(parent):
            row = ctk.CTkFrame(parent, fg_color='transparent', corner_radius=0)
            row.pack(fill=tk.X, padx=16, pady=4)
            return row

        def _sep(parent):
            ctk.CTkFrame(parent, fg_color=C['border'], height=1, corner_radius=999).pack(fill=tk.X, padx=16, pady=8)

        c1 = _card(insp_inner, '파일 및 엔진')
        self.btn_open = _ctk_button(c1, '영상 파일 선택', self.on_select_video, kind='secondary', height=42)
        self.btn_open.pack(fill=tk.X, padx=16, pady=(0, 8))
        r = _row(c1)
        ctk.CTkLabel(r, text='AI 모델', text_color=C['text2'], font=_f).pack(side=tk.LEFT)
        self.ai_model_var = tk.StringVar(value='large-v3-turbo (Default)')
        self.ai_model_combo = ctk.CTkComboBox(r, variable=self.ai_model_var, values=['large-v3-turbo (Default)', 'models/Whisper-Large-v3-turbo-STT-Zeroth-KO-v2 (Local Zeroth)', 'models/whisper-medium-ko-zeroth (Medium-Zeroth)'], width=250, command=lambda _=None: self.reset_action_button())
        self.ai_model_combo.pack(side=tk.RIGHT)
        _sep(c1)
        r = _row(c1)
        ctk.CTkLabel(r, text='장치', text_color=C['text2'], font=_f).pack(side=tk.LEFT)
        self.device_var = tk.StringVar(value='CPU (50%)')
        self.device_combo = ctk.CTkComboBox(r, variable=self.device_var, values=['Auto', 'NVIDIA (cuda)', 'Apple Mac (mps)', 'CPU (25%)', 'CPU (50%)', 'CPU (75%)'], width=180)
        self.device_combo.pack(side=tk.RIGHT)
        r = _row(c1)
        ctk.CTkLabel(r, text='언어', text_color=C['text2'], font=_f).pack(side=tk.LEFT)
        self.lang_var = tk.StringVar(value='Korean (ko)')
        self.lang_combo = ctk.CTkComboBox(r, variable=self.lang_var, values=['Korean (ko)', 'English (en)', 'Japanese (ja)', 'Chinese (zh)', 'Auto Detect'], width=180)
        self.lang_combo.pack(side=tk.RIGHT)

        c2 = _card(insp_inner, '분석')
        self.mode_var = tk.StringVar(value='Speech to Text')
        self.mode_combo = ctk.CTkComboBox(c2, variable=self.mode_var, values=['Speech to Text', 'Speech + Cut Edit', 'Peak Search', 'Silence Removal (VAD)', 'Auto Chapter Split (CLIP)'])
        self.mode_combo.pack(fill=tk.X, padx=16, pady=(0, 8))

        def _check_mode(*_):
            mode = self.mode_var.get()
            if mode in ['Speech + Cut Edit', 'Auto Chapter Split (CLIP)']:
                messagebox.showinfo('안내', '이 모드는 아직 준비되지 않았습니다.')
                self.mode_var.set('Speech to Text')
            self.reset_action_button()

        self.mode_var.trace_add('write', _check_mode)
        self.btn_analyze = _ctk_button(c2, '분석 시작', self.on_start_analysis, kind='primary', height=44)
        self.btn_analyze.pack(fill=tk.X, padx=16, pady=(0, 6))
        self.btn_stop = _ctk_button(c2, '작업 중지', self.on_stop_action, kind='danger', height=38)
        self.btn_stop.pack(fill=tk.X, padx=16)
        self.btn_stop.configure(state=tk.DISABLED)
        self.lbl_status = LblMarquee(c2, text='준비 완료', fg=C['green'], bg=C['bg2'], font=_f)
        self.lbl_status.pack(fill=tk.X, padx=16, pady=(8, 0))
        self.progress_var = tk.DoubleVar()
        ttk.Progressbar(c2, variable=self.progress_var).pack(fill=tk.X, padx=16, pady=(6, 0))
        self.use_burn_sub_var = tk.BooleanVar(value=False)
        self.save_frame = ctk.CTkFrame(c2, fg_color='transparent', corner_radius=0)
        self.save_frame.pack(fill=tk.X, padx=16, pady=6)
        self.save_frame.pack_forget()
        self.use_burn_sub_checkbox = ctk.CTkCheckBox(self.save_frame, text='Burn subtitles into video (Re-encode)', variable=self.use_burn_sub_var)
        self.use_burn_sub_checkbox.pack(anchor=tk.W, pady=(0, 6))
        btn_box = ctk.CTkFrame(self.save_frame, fg_color='transparent', corner_radius=0)
        btn_box.pack(fill=tk.X)
        self.btn_fast_save = _ctk_button(btn_box, 'Fast Render', lambda: self.start_export(fast=True), kind='purple', height=38)
        self.btn_fast_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        self.btn_pro_save = _ctk_button(btn_box, 'Precise Render', lambda: self.start_export(fast=False), kind='secondary', height=38)
        self.btn_pro_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))

        c3 = _card(insp_inner, 'Recognition Options')
        self.beam_size_var = tk.IntVar(value=5)
        self.use_denoise_var = tk.BooleanVar(value=False)
        self.use_dominant_var = tk.BooleanVar(value=False)
        self.remove_punctuation_var = tk.BooleanVar(value=True)
        self.use_silero_vad_var = tk.BooleanVar(value=False)
        self.use_whisper_vad_var = tk.BooleanVar(value=False)
        self.use_whisperx_var = tk.BooleanVar(value=False)
        self.remove_punc_check = ctk.CTkCheckBox(c3, text='Remove punctuation', variable=self.remove_punctuation_var)
        self.remove_punc_check.pack(anchor=tk.W, padx=16, pady=(0, 4))
        _sep(c3)
        self.silero_check = ctk.CTkCheckBox(c3, text='External VAD (Silero)', variable=self.use_silero_vad_var)
        self.silero_check.pack(anchor=tk.W, padx=16, pady=2)
        self.whisper_vad_check = ctk.CTkCheckBox(c3, text='Internal VAD (Whisper)', variable=self.use_whisper_vad_var)
        self.whisper_vad_check.pack(anchor=tk.W, padx=16, pady=2)
        self.whisperx_check = ctk.CTkCheckBox(c3, text='WhisperX word sync correction', variable=self.use_whisperx_var)
        self.whisperx_check.pack(anchor=tk.W, padx=16, pady=2)

        def _check_whisperx(*_):
            if self.use_whisperx_var.get():
                messagebox.showinfo('안내', 'WhisperX는 아직 지원되지 않습니다.')
                self.use_whisperx_var.set(False)

        self.use_whisperx_var.trace_add('write', _check_whisperx)
        _sep(c3)
        r = _row(c3)
        ctk.CTkLabel(r, text='Silence Length', text_color=C['text2'], font=_f).pack(side=tk.LEFT)
        self.silence_dur_var = tk.DoubleVar(value=2.0)
        self.silence_entry = ctk.CTkEntry(r, textvariable=self.silence_dur_var, width=90)
        self.silence_entry.pack(side=tk.RIGHT)
        r = _row(c3)
        ctk.CTkLabel(r, text='Speech Padding', text_color=C['text2'], font=_f).pack(side=tk.LEFT)
        self.speech_pad_var = tk.DoubleVar(value=0.1)
        self.pad_entry = ctk.CTkEntry(r, textvariable=self.speech_pad_var, width=90)
        self.pad_entry.pack(side=tk.RIGHT)
        r = _row(c3)
        ctk.CTkLabel(r, text='VAD Threshold', text_color=C['text2'], font=_f).pack(side=tk.LEFT)
        self.vad_threshold_var = tk.DoubleVar(value=0.35)
        self.vad_slider = ctk.CTkSlider(r, from_=0.1, to=0.9, variable=self.vad_threshold_var, width=140)
        self.vad_slider.pack(side=tk.RIGHT)
        r = _row(c3)
        ctk.CTkLabel(r, text='Subtitle Length', text_color=C['text2'], font=_f).pack(side=tk.LEFT)
        self.max_len_int = tk.IntVar(value=20)
        self.max_len_slider = ctk.CTkSlider(r, from_=10, to=50, variable=self.max_len_int, number_of_steps=40, width=140)
        self.max_len_slider.pack(side=tk.RIGHT)

        cs = self.tab_style
        st_inner = ctk.CTkFrame(cs, fg_color='transparent', corner_radius=0)
        st_inner.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        def _st_row(label):
            fr = ctk.CTkFrame(st_inner, fg_color='transparent', corner_radius=0)
            fr.pack(fill=tk.X, pady=8)
            ctk.CTkLabel(fr, text=label, text_color=C['text'], font=_fb, width=150, anchor='w').pack(side=tk.LEFT)
            return fr

        self._sub_debounce = None
        def _update_sub(*_):
            if self._sub_debounce:
                self.root.after_cancel(self._sub_debounce)
            self._sub_debounce = self.root.after(200, lambda: self.apply_preview_subtitles(force_reload=True))

        self._sub_font_name = tk.StringVar(value='Malgun Gothic')
        class _FontProxy:
            def __init__(self, var): self._var = var
            def get(self): return self._var.get()
            def set(self, v): self._var.set(v)
        self.sub_font = _FontProxy(self._sub_font_name)

        r = _st_row('Font Name')
        self._font_btn = _ctk_button(r, 'Choose Font', self._open_font_picker, kind='secondary', height=34, width=180)
        self._font_btn.pack(side=tk.LEFT)
        self._sub_font_name.trace_add('write', lambda *_: [self._font_btn.configure(text=self._sub_font_name.get()), _update_sub()])

        self.sub_font_size = tk.IntVar(value=80)
        r = _st_row('Font Size')
        self.sub_font_size_slider = ctk.CTkSlider(r, from_=10, to=200, variable=self.sub_font_size, number_of_steps=190, width=260)
        self.sub_font_size_slider.pack(side=tk.LEFT)
        self.sub_font_size.trace_add('write', _update_sub)

        self.sub_color_f = tk.StringVar(value='#FFFFFF')
        r = _st_row('Text Color')
        def _pick_f():
            c = tk.colorchooser.askcolor(initialcolor=self.sub_color_f.get())[1]
            if c:
                self.sub_color_f.set(c)
                _update_sub()
        self.sub_color_f_btn = _ctk_button(r, 'Choose Color', _pick_f, kind='secondary', height=32, width=150)
        self.sub_color_f_btn.pack(side=tk.LEFT)
        ctk.CTkLabel(r, textvariable=self.sub_color_f, text_color=C['text2'], font=_f).pack(side=tk.LEFT, padx=12)

        self.sub_outline = tk.IntVar(value=3)
        r = _st_row('Outline Width')
        self.sub_outline_slider = ctk.CTkSlider(r, from_=0, to=15, variable=self.sub_outline, number_of_steps=15, width=260)
        self.sub_outline_slider.pack(side=tk.LEFT)
        self.sub_outline.trace_add('write', _update_sub)

        self.sub_color_o = tk.StringVar(value='#000000')
        r = _st_row('Outline Color')
        def _pick_o():
            c = tk.colorchooser.askcolor(initialcolor=self.sub_color_o.get())[1]
            if c:
                self.sub_color_o.set(c)
                _update_sub()
        self.sub_color_o_btn = _ctk_button(r, 'Choose Color', _pick_o, kind='secondary', height=32, width=150)
        self.sub_color_o_btn.pack(side=tk.LEFT)
        ctk.CTkLabel(r, textvariable=self.sub_color_o, text_color=C['text2'], font=_f).pack(side=tk.LEFT, padx=12)

        self.sub_shadow = tk.IntVar(value=3)
        r = _st_row('Shadow Depth')
        self.sub_shadow_slider = ctk.CTkSlider(r, from_=0, to=15, variable=self.sub_shadow, number_of_steps=15, width=260)
        self.sub_shadow_slider.pack(side=tk.LEFT)
        self.sub_shadow.trace_add('write', _update_sub)

        self.sub_color_s = tk.StringVar(value='#000000')
        r = _st_row('Shadow Color')
        def _pick_s():
            c = tk.colorchooser.askcolor(initialcolor=self.sub_color_s.get())[1]
            if c:
                self.sub_color_s.set(c)
                _update_sub()
        self.sub_color_s_btn = _ctk_button(r, 'Choose Color', _pick_s, kind='secondary', height=32, width=150)
        self.sub_color_s_btn.pack(side=tk.LEFT)
        ctk.CTkLabel(r, textvariable=self.sub_color_s, text_color=C['text2'], font=_f).pack(side=tk.LEFT, padx=12)

        self.sub_y_pos = tk.IntVar(value=50)
        r = _st_row('Subtitle Y Position')
        self.sub_y_pos_slider = ctk.CTkSlider(r, from_=0, to=400, variable=self.sub_y_pos, number_of_steps=400, width=260)
        self.sub_y_pos_slider.pack(side=tk.LEFT)
        self.sub_y_pos.trace_add('write', _update_sub)

        c4 = _card(insp_inner, 'Export')
        r = _row(c4)
        ctk.CTkLabel(r, text='Format', text_color=C['text2'], font=_f).pack(side=tk.LEFT)
        self.export_format = tk.StringVar(value='SRT')
        self.export_format_combo = ctk.CTkComboBox(r, variable=self.export_format, values=['SRT', 'VTT', 'TXT', 'CSV', 'FCPXML'], width=140)
        self.export_format_combo.pack(side=tk.RIGHT)
        self.btn_export_ass = _ctk_button(c4, '자막 내보내기', self.export_subtitles, kind='orange', height=38)
        self.btn_export_ass.pack(fill=tk.X, padx=16, pady=(8, 14))

        self.menu = tk.Menu(self.root, tearoff=0, bg=C['bg2'], fg=C['text'], activebackground=C['accent'], activeforeground='white', font=_f)
        self.menu.add_command(label='시작 지점으로 이동', command=self.jump_to_start)
        self.menu.add_command(label='종료 지점으로 이동', command=self.jump_to_end)
        self.menu.add_separator()
        self.menu.add_command(label='선택 대사 수정', command=self.edit_selected_text)
        
        self.tree.bind('<ButtonRelease-1>', self.on_tree_click)
        self.tree.bind('<Button-3>', self.show_context_menu)

        # [Apple HIG] PanedWindow ?몃뱾 ?쒓컖??(Vrew ?ㅽ???

        # [Ctrl+?? ?먮쭑 ?쒖옉/醫낅즺 ?쒓컙 짹50ms 誘몄꽭 議곗젙 (Apple HIG)
        def _on_ctrl_wheel(e):
            if not (e.state & 0x4): return # Ctrl ???뚮┝ -> 湲곕낯 ?ㅽ겕濡??덉슜
            
            # [?ъ슜???붿껌] Ctrl ?뚮┛ 寃쎌슦, ?쒓컙 議곗젅 媛???곸뿭???꾨땲?붾씪???ㅽ겕濡?李⑤떒
            item = self.tree.identify_row(e.y)
            col = self.tree.identify_column(e.x)
            if item and col in ('#2', '#3'):
                try:
                    idx = int(self.tree.item(item)['values'][0]) - 1
                    if 0 <= idx < len(self.results_data):
                        # ??諛⑺뼢 諛섏쟾: ?꾨줈(delta>0) ?щ━硫??쒓컙 媛먯냼(-), ?꾨옒濡?delta<0) ?대━硫??쒓컙 利앷?(+)
                        delta = -0.05 if e.delta > 0 else 0.05
                        key = 's' if col == '#2' else 'e'
                        nv = max(0, self.results_data[idx][key] + delta)
                        
                        # ?덉쟾?μ튂 諛?李⑤떒 濡쒖쭅
                        valid = True
                        if key == 's':
                            if nv >= self.results_data[idx]['e'] or (idx > 0 and nv < self.results_data[idx-1]['e']): valid = False
                        else: # key == 'e'
                            if nv <= self.results_data[idx]['s'] or (idx < len(self.results_data)-1 and nv > self.results_data[idx+1]['s']): valid = False
                        
                        if valid:
                            self.transcript_manager.save_state()
                            self.results_data[idx][key] = round(nv, 3)
                            
                            # [?쒕땲??理쒖쟻?? ?대? ?⑥뼱 ??꾩뒪?ы봽 ?숆린??(Word Block 酉곗? ?쇨????좎?)
                            words = self.results_data[idx].get('words', [])
                            if words:
                                if key == 's': words[0]['s'] = nv
                                else: words[-1]['e'] = nv

                            self.tree.set(item, column=col, value=self.format_time(nv))
                            self.player.set_time(int(nv * 1000))
                            self.player.play()
                            self.apply_preview_subtitles(force_reload=True)
                except Exception as e: print(f'[WARN] Ctrl+???쒓컙 議곗젅 ?ㅻ쪟: {e}')
            return 'break' # Ctrl ?뚮┛ ?곹깭?먯꽑 議곗젅 ?깃났 ?щ?? 臾닿??섍쾶 ?ㅽ겕濡?諛⑹?
        self.tree.bind('<MouseWheel>', _on_ctrl_wheel)


        






    def _open_font_picker(self):
        """?쒖뒪???고듃 ?꾩껜瑜??먯껜 ?쒖껜濡?誘몃━蹂닿린?섎ŉ 寃???좏깮?섎뒗 ?앹뾽"""
        popup = tk.Toplevel(self.root)
        popup.title("?고듃 ?좏깮")
        popup.geometry("380x500")
        popup.configure(bg=self.C['bg'])
        popup.transient(self.root)
        popup.grab_set()
        
        # ?쒖뒪???고듃 紐⑸줉 (以묐났 ?쒓굅 + ?뺣젹)
        all_fonts = sorted(set(tkfont.families()), key=str.lower)
        
        # 寃???낅젰李?
        search_var = tk.StringVar()
        search_entry = tk.Entry(popup, textvariable=search_var, font=('Noto Sans KR', 11), bg=self.C['bg2'], fg=self.C['text'], insertbackground=self.C['text'], relief=tk.FLAT)
        search_entry.pack(fill=tk.X, padx=14, pady=(14, 8))
        search_entry.focus_set()
        
        # ?고듃 由ъ뒪??(Text ?꾩젽 + ?ㅽ겕濡ㅻ컮)
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
            """?꾩옱 ?ъ빱?ㅺ? ?띿뒪???몄쭛 ?꾩젽???덉쑝硫?True (???대깽??李⑤떒)"""
            w = self.root.focus_get()
            return isinstance(w, (tk.Entry, tk.Text))

        def _on_space(e):
            if _is_editing(): return  # ?몄쭛 以묒뿏 ?ㅽ럹?댁뒪諛붾? ?꾩젽???섍?
            self.toggle_play()
            return "break"

        def _on_left(e):
            if _is_editing(): return  # ?몄쭛 以묒뿏 醫뚮갑?ν궎瑜??꾩젽???섍?
            self.skip_time(-5000)
            return "break"

        def _on_right(e):
            if _is_editing(): return  # ?몄쭛 以묒뿏 ?곕갑?ν궎瑜??꾩젽???섍?
            self.skip_time(5000)
            return "break"

        def _on_undo(e):
            if _is_editing(): return # ?몄쭛 以묒씤 ?띿뒪?몄쓽 undo???쒖뒪?쒖뿉 留↔?
            if self.transcript_manager.undo():
                self.rebuild_tree_and_render()
            return "break"
            
        def _on_redo(e):
            if _is_editing(): return
            if self.transcript_manager.redo():
                self.rebuild_tree_and_render()
            return "break"

        self.root.bind_all("<space>", _on_space)
        self.root.bind_all("<Left>",  _on_left)
        self.root.bind_all("<Right>", _on_right)
        self.root.bind_all("<Control-z>", _on_undo)
        self.root.bind_all("<Control-y>", _on_redo)
        self.root.bind_all("<Control-Z>", _on_redo) # Shift+Z

        # [?ъ슜???붿껌] ??씠??由ъ뒪?몄뿉 ?ъ빱?ㅺ? ?덉쓣 ??諛⑺뼢?ㅻ줈 硫붾돱媛 ?섏뼱媛??Tkinter 湲곕낯 ?숈옉 李⑤떒
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

    def reset_action_button(self):
        self.save_frame.pack_forget()
        self.btn_analyze.configure(text='분석 시작', command=self.on_start_analysis, state=tk.NORMAL)
        self.btn_fast_save.configure(state=tk.NORMAL)
        self.btn_pro_save.configure(state=tk.NORMAL)

    def reset_for_new_video(self):
        """Clear previous analysis state when selecting a new video."""
        self.stop_event.set()
        self.stop_event = threading.Event()
        self.results_data = []
        self.tree.delete(*self.tree.get_children())
        self.progress_var.set(0)
        self.seek_var.set(0)
        self.lbl_time.config(text='00:00 / 00:00')
        self.btn_stop.configure(state=tk.DISABLED)
        self._last_active_idx = -2
        self.overlay_manager.set_selected(None)
        if hasattr(self, 'block_editor'):
            self.block_editor.render_block_view()
        self.refresh_overlay_preview()
        self.refresh_overlay_timeline()
        self.refresh_overlay_property_panel()

    def _get_overlay_time(self):
        if self.player:
            curr_ms = self.player.get_time()
            if curr_ms >= 0:
                return curr_ms / 1000.0
        return 0.0

    def add_image_overlay(self):
        image_path = filedialog.askopenfilename(filetypes=[('Image files', '*.png *.jpg *.jpeg *.bmp *.webp')])
        if not image_path:
            return
        start_time = self._get_overlay_time()
        end_time = start_time + 3.0
        item = self.overlay_manager.create_image_overlay(image_path, start_time, end_time)
        self.overlay_manager.set_selected(item.id)
        self.refresh_overlay_preview(start_time)
        self.refresh_overlay_timeline()
        self.refresh_overlay_property_panel()
        self.notebook.select(self.tab_overlay)

    def add_text_overlay(self):
        start_time = self._get_overlay_time()
        end_time = start_time + 3.0
        item = self.overlay_manager.create_text_overlay('Sample Text', start_time, end_time)
        self.overlay_manager.set_selected(item.id)
        self.refresh_overlay_preview(start_time)
        self.refresh_overlay_timeline()
        self.refresh_overlay_property_panel()
        self.notebook.select(self.tab_overlay)

    def _fmt_overlay_prop(self, value, digits=2):
        try:
            return f"{float(value):.{digits}f}"
        except Exception:
            return ''

    def _get_subtitle_adapter_items(self):
        if not getattr(self, 'use_subtitle_adapter_var', None) or not self.use_subtitle_adapter_var.get():
            return []
        if not self.results_data:
            return []
        font_size = self.sub_font_size.get() if hasattr(self, 'sub_font_size') else 40
        text_color = self.sub_color_f.get() if hasattr(self, 'sub_color_f') else '#FFFFFF'
        margin_v = self.sub_y_pos.get() if hasattr(self, 'sub_y_pos') else 50
        return build_subtitle_overlays(
            self.results_data,
            self.overlay_manager.render_width,
            self.overlay_manager.render_height,
            font_size=float(font_size),
            text_color=str(text_color),
            margin_v=int(margin_v),
            track_index=max(1, len(self.overlay_manager.tracks)),
            overrides=self.subtitle_adapter_overrides,
        )

    def _get_timeline_items(self):
        return self.overlay_manager.get_all_items() + self._get_subtitle_adapter_items()

    def _get_any_overlay_item(self, item_id):
        item = self.overlay_manager.get_item(item_id)
        if item is not None:
            return item
        for sub_item in self._get_subtitle_adapter_items():
            if sub_item.id == item_id:
                return sub_item
        return None

    def _get_subtitle_segment_index(self, item):
        if not item or item.type != 'subtitle':
            return None
        extra = getattr(item, 'extra', {}) or {}
        idx = extra.get('segment_index')
        return idx if isinstance(idx, int) else None

    def _apply_item_timeline_times(self, item, start_time, end_time):
        start_time = max(0.0, float(start_time))
        end_time = max(start_time, float(end_time))
        if item.type == 'subtitle':
            idx = self._get_subtitle_segment_index(item)
            if idx is None:
                return
            ov = dict(self.subtitle_adapter_overrides.get(idx, {}))
            ov['start_time'] = start_time
            ov['end_time'] = end_time
            self.subtitle_adapter_overrides[idx] = ov
        else:
            item.start_time = start_time
            item.end_time = end_time

    def refresh_overlay_property_panel(self):
        selected = self._get_any_overlay_item(self.overlay_manager.selected_item_id)
        if selected is None:
            for key, var in self.overlay_prop_vars.items():
                if key == 'visible':
                    var.set(False)
                else:
                    var.set('')
            self.lbl_overlay_props.config(text='선택된 오버레이가 없습니다')
            for ent in self.overlay_prop_entries.values():
                ent.configure(state=tk.DISABLED)
            for btn in [self.btn_apply_overlay_props, self.btn_overlay_forward, self.btn_overlay_backward, self.btn_overlay_front, self.btn_overlay_back, self.overlay_visible_check]:
                btn.configure(state=tk.DISABLED)
            return
        values = {
            'text': selected.text or '',
            'x': self._fmt_overlay_prop(selected.x, 0),
            'y': self._fmt_overlay_prop(selected.y, 0),
            'width': self._fmt_overlay_prop(selected.width, 0),
            'height': self._fmt_overlay_prop(selected.height, 0),
            'start_time': self._fmt_overlay_prop(selected.start_time, 2),
            'end_time': self._fmt_overlay_prop(selected.end_time, 2),
            'opacity': self._fmt_overlay_prop(selected.opacity, 2),
            'font_size': self._fmt_overlay_prop(selected.font_size, 0),
            'text_color': selected.text_color or '#FFFFFF',
            'rotation': self._fmt_overlay_prop(selected.rotation, 1),
        }
        for key, value in values.items():
            self.overlay_prop_vars[key].set(value)
        self.overlay_prop_vars['visible'].set(bool(selected.visible))
        vis_text = '켜짐' if selected.visible else '꺼짐'
        name = selected.text if selected.type == 'text' else os.path.basename(selected.source or selected.id)
        self.lbl_overlay_props.config(text=f'선택: {name}\n유형: {selected.type}\n레이어: {selected.layer_index}\n표시: {vis_text}')
        for key, ent in self.overlay_prop_entries.items():
            if key in ('text', 'font_size', 'text_color') and selected.type != 'text':
                ent.configure(state=tk.DISABLED)
            elif key == 'rotation' and selected.type != 'image':
                ent.configure(state=tk.DISABLED)
            else:
                ent.configure(state=tk.NORMAL)
        for btn in [self.btn_apply_overlay_props, self.btn_overlay_forward, self.btn_overlay_backward, self.btn_overlay_front, self.btn_overlay_back, self.overlay_visible_check]:
            btn.configure(state=tk.NORMAL)

    def apply_selected_overlay_properties(self):
        selected = self._get_any_overlay_item(self.overlay_manager.selected_item_id)
        if selected is None:
            return
        try:
            if selected.type != 'subtitle':
                selected.x = max(0.0, float(self.overlay_prop_vars['x'].get()))
            if selected.type != 'subtitle':
                selected.y = max(0.0, float(self.overlay_prop_vars['y'].get()))
                selected.width = max(16.0, float(self.overlay_prop_vars['width'].get()))
                selected.height = max(16.0, float(self.overlay_prop_vars['height'].get()))
                if selected.type == 'image':
                    selected.rotation = float(self.overlay_prop_vars['rotation'].get() or selected.rotation or 0.0)
            start_time = max(0.0, float(self.overlay_prop_vars['start_time'].get()))
            end_time = max(start_time, float(self.overlay_prop_vars['end_time'].get()))
            if selected.type == 'subtitle':
                idx = self._get_subtitle_segment_index(selected)
                if idx is None:
                    return
                ov = dict(self.subtitle_adapter_overrides.get(idx, {}))
                ov['start_time'] = start_time
                ov['end_time'] = end_time
                ov['visible'] = bool(self.overlay_prop_vars['visible'].get())
                ov['font_size'] = max(8.0, float(self.overlay_prop_vars['font_size'].get() or selected.font_size or 48))
                color = self.overlay_prop_vars['text_color'].get().strip() or '#FFFFFF'
                if not color.startswith('#') or len(color) not in (4, 7):
                    raise ValueError
                ov['text_color'] = color
                self.subtitle_adapter_overrides[idx] = ov
            else:
                selected.start_time = start_time
                selected.end_time = end_time
                selected.opacity = max(0.0, min(1.0, float(self.overlay_prop_vars['opacity'].get())))
                selected.visible = bool(self.overlay_prop_vars['visible'].get())
            if selected.type == 'text':
                selected.text = self.overlay_prop_vars['text'].get()
                selected.font_size = max(8.0, float(self.overlay_prop_vars['font_size'].get() or 48))
                color = self.overlay_prop_vars['text_color'].get().strip() or '#FFFFFF'
                if not color.startswith('#') or len(color) not in (4, 7):
                    raise ValueError
                selected.text_color = color
        except ValueError:
            messagebox.showerror('오류', '오버레이 속성은 올바른 숫자여야 합니다.')
            return
        self._invalidate_overlay_preview_cache(selected.id)
        self.refresh_overlay_preview()
        self.refresh_overlay_timeline()
        self.refresh_overlay_property_panel()

    def on_toggle_selected_overlay_visible(self):
        selected = self._get_any_overlay_item(self.overlay_manager.selected_item_id)
        if selected is None:
            return
        if selected.type == 'subtitle':
            idx = self._get_subtitle_segment_index(selected)
            if idx is None:
                return
            ov = dict(self.subtitle_adapter_overrides.get(idx, {}))
            ov['visible'] = bool(self.overlay_prop_vars['visible'].get())
            self.subtitle_adapter_overrides[idx] = ov
        else:
            selected.visible = bool(self.overlay_prop_vars['visible'].get())
        self.refresh_overlay_preview()
        self.refresh_overlay_timeline()
        self.refresh_overlay_property_panel()

    def delete_selected_overlay(self):
        selected = self.overlay_manager.get_selected()
        if selected is None or selected.type == 'subtitle':
            return
        item_id = selected.id
        self.overlay_manager.remove_item(item_id)
        widget = self._overlay_label_refs.pop(item_id, None)
        if widget is not None and widget.winfo_exists():
            widget.destroy()
        refs = self._overlay_canvas_refs.pop(item_id, None)
        if refs:
            for canvas_id in refs.get('markers', []):
                try:
                    self.preview_overlay_canvas.delete(canvas_id)
                except tk.TclError:
                    pass
            image_id = refs.get('image')
            if image_id:
                try:
                    self.preview_overlay_canvas.delete(image_id)
                except tk.TclError:
                    pass
        self._overlay_photo_refs.pop(item_id, None)
        self._invalidate_overlay_preview_cache(item_id)
        self.overlay_manager.set_selected(None)
        self.refresh_overlay_preview()
        self.refresh_overlay_timeline()
        self.refresh_overlay_property_panel()

    def reorder_selected_overlay(self, direction):
        if self.overlay_manager.move_selected_layer(direction):
            self.refresh_overlay_preview()
            self.refresh_overlay_timeline()
            self.refresh_overlay_property_panel()

    def _get_video_viewport_rect(self):
        frame_w = max(1, self.video_frame.winfo_width())
        frame_h = max(1, self.video_frame.winfo_height())
        render_w = max(1, int(getattr(self.overlay_manager, 'render_width', 1920) or 1920))
        render_h = max(1, int(getattr(self.overlay_manager, 'render_height', 1080) or 1080))
        frame_ratio = frame_w / frame_h
        render_ratio = render_w / render_h
        if frame_ratio > render_ratio:
            viewport_h = frame_h
            viewport_w = int(round(viewport_h * render_ratio))
            viewport_x = (frame_w - viewport_w) // 2
            viewport_y = 0
        else:
            viewport_w = frame_w
            viewport_h = int(round(viewport_w / render_ratio))
            viewport_x = 0
            viewport_y = (frame_h - viewport_h) // 2
        return viewport_x, viewport_y, max(1, viewport_w), max(1, viewport_h)

    def _get_overlay_preview_size(self):
        _, _, w, h = self._get_video_viewport_rect()
        return w, h

    def _get_overlay_layer_geometry(self):
        viewport_x, viewport_y, viewport_w, viewport_h = self._get_video_viewport_rect()
        return (
            self.video_frame.winfo_rootx() + viewport_x,
            self.video_frame.winfo_rooty() + viewport_y,
            viewport_w,
            viewport_h,
        )

    def _update_overlay_layer_window(self):
        if not hasattr(self, 'preview_overlay_window') or not self.preview_overlay_window.winfo_exists():
            return
        x, y, w, h = self._get_overlay_layer_geometry()
        if w <= 1 or h <= 1:
            self.preview_overlay_window.withdraw()
            return
        self.preview_overlay_window.geometry(f'{w}x{h}+{x}+{y}')
        self.preview_overlay_window.deiconify()
        self.preview_overlay_window.lift(self.root)
        self.preview_overlay_canvas.configure(width=w, height=h)

    def _get_overlay_cache_key(self, item_id, width, height):
        return (item_id, int(width), int(height))

    def _hex_to_rgba(self, color, opacity=1.0):
        color = (color or '#FFFFFF').strip()
        if not color.startswith('#'):
            color = '#FFFFFF'
        if len(color) == 4:
            color = '#' + ''.join(ch * 2 for ch in color[1:])
        try:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
        except Exception:
            r, g, b = 255, 255, 255
        a = int(max(0.0, min(1.0, opacity)) * 255)
        return (r, g, b, a)

    def _get_preview_text_font(self, size):
        for name in ['malgun.ttf', 'arial.ttf', 'segoeui.ttf']:
            path = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts', name)
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size=size)
                except Exception:
                    pass
        return ImageFont.load_default()

    def _get_overlay_source_image(self, source):
        if not source or not os.path.exists(source):
            return None
        cached = self._overlay_source_image_cache.get(source)
        if cached is not None:
            return cached
        img = Image.open(source).convert('RGBA')
        self._overlay_source_image_cache[source] = img
        return img

    def _invalidate_overlay_preview_cache(self, item_id):
        self._overlay_preview_cache = {k: v for k, v in self._overlay_preview_cache.items() if k[0] != item_id}

    def _sample_image_fill_rgba(self, src):
        width, height = src.size
        pts = [
            src.getpixel((0, 0)),
            src.getpixel((max(0, width - 1), 0)),
            src.getpixel((0, max(0, height - 1))),
            src.getpixel((max(0, width - 1), max(0, height - 1))),
        ]
        r = int(sum(p[0] for p in pts) / len(pts))
        g = int(sum(p[1] for p in pts) / len(pts))
        b = int(sum(p[2] for p in pts) / len(pts))
        a = int(sum(p[3] for p in pts) / len(pts))
        return (r, g, b, a)

    def _remove_preview_matte(self, src, tolerance=18):
        """Remove border-connected flat background from opaque preview assets.

        This is preview-only cleanup so rotated ImageOverlay objects do not show a
        rectangular plate when the source is a flat screenshot/card on a solid matte.
        """
        if src is None:
            return None
        alpha_min, alpha_max = src.getchannel('A').getextrema()
        if alpha_min < 255:
            return src
        cache_key = (id(src), src.size, tolerance)
        cached = self._overlay_preview_source_cache.get(cache_key)
        if cached is not None:
            return cached

        arr = np.array(src, dtype=np.uint8)
        if arr.size == 0:
            return src
        h, w = arr.shape[:2]
        corner_rgb = np.array(self._sample_image_fill_rgba(src)[:3], dtype=np.int16)
        rgb = arr[:, :, :3].astype(np.int16)
        close = np.all(np.abs(rgb - corner_rgb) <= tolerance, axis=2)
        if not close.any():
            self._overlay_preview_source_cache[cache_key] = src
            return src

        visited = np.zeros((h, w), dtype=bool)
        q = []
        for x in range(w):
            if close[0, x]:
                q.append((0, x))
            if close[h - 1, x]:
                q.append((h - 1, x))
        for y in range(h):
            if close[y, 0]:
                q.append((y, 0))
            if close[y, w - 1]:
                q.append((y, w - 1))

        while q:
            y, x = q.pop()
            if visited[y, x] or not close[y, x]:
                continue
            visited[y, x] = True
            if y > 0: q.append((y - 1, x))
            if y + 1 < h: q.append((y + 1, x))
            if x > 0: q.append((y, x - 1))
            if x + 1 < w: q.append((y, x + 1))

        keep_mask = ~visited
        if keep_mask.sum() < max(64, int(w * h * 0.02)):
            self._overlay_preview_source_cache[cache_key] = src
            return src

        arr2 = arr.copy()
        arr2[visited, 3] = 0
        cleaned = Image.fromarray(arr2, 'RGBA')
        bbox = cleaned.getchannel('A').getbbox()
        if bbox:
            cleaned = cleaned.crop(bbox)
        self._overlay_preview_source_cache[cache_key] = cleaned
        return cleaned

    def _build_overlay_preview_image(self, item, width, height, draft=False):
        width = max(1, int(width))
        height = max(1, int(height))
        if item.type == 'image':
            src = self._get_overlay_source_image(item.source)
            if src is None:
                return None
            resample = Image.BILINEAR if draft else Image.LANCZOS
            img = src.resize((width, height), resample)
            rotation = float(getattr(item, 'rotation', 0.0) or 0.0)
            if abs(rotation) > 0.01:
                img = img.rotate(-rotation, expand=True, resample=Image.BICUBIC if not draft else Image.BILINEAR, fillcolor=(0, 0, 0, 0))
            opacity = max(0.0, min(1.0, float(getattr(item, 'opacity', 1.0) or 1.0)))
            if opacity < 0.999:
                alpha = img.getchannel('A').point(lambda value: int(value * opacity))
                img.putalpha(alpha)
            alpha_bbox = img.getchannel('A').getbbox()
            if alpha_bbox:
                img = img.crop(alpha_bbox)
            return img
        if item.type in ('text', 'subtitle'):
            img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            font = self._get_preview_text_font(max(8, int(item.font_size)))
            draw.multiline_text((6, 6), item.text or '', font=font, fill=self._hex_to_rgba(item.text_color, item.opacity), spacing=4)
            return img
        return None

    def _rotate_overlay_point(self, cx, cy, px, py, rotation_deg):
        theta = math.radians(-(float(rotation_deg or 0.0)))
        dx = px - cx
        dy = py - cy
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        return (
            cx + (dx * cos_t) - (dy * sin_t),
            cy + (dx * sin_t) + (dy * cos_t),
        )

    def _get_image_overlay_geometry(self, item, preview_w, preview_h):
        x, y, w, h = self.overlay_manager.preview_rect(item, preview_w, preview_h)
        cx = x + (w / 2.0)
        cy = y + (h / 2.0)
        base_corners = [
            (x, y),
            (x + w, y),
            (x + w, y + h),
            (x, y + h),
        ]
        corners = [self._rotate_overlay_point(cx, cy, px, py, getattr(item, 'rotation', 0.0)) for px, py in base_corners]
        xs = [pt[0] for pt in corners]
        ys = [pt[1] for pt in corners]
        bbox = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        return {
            'center': (cx, cy),
            'base_rect': (x, y, w, h),
            'corners': corners,
            'bbox': bbox,
        }

    def _point_in_polygon(self, x, y, corners):
        inside = False
        n = len(corners)
        for i in range(n):
            x1, y1 = corners[i]
            x2, y2 = corners[(i + 1) % n]
            if ((y1 > y) != (y2 > y)):
                xinters = (x2 - x1) * (y - y1) / max(1e-9, (y2 - y1)) + x1
                if x < xinters:
                    inside = not inside
        return inside

    def _distance_sq(self, p1, p2):
        dx = p1[0] - p2[0]
        dy = p1[1] - p2[1]
        return dx * dx + dy * dy

    def _offset_corner_handle(self, center, corner, distance):
        cx, cy = center
        px, py = corner
        dx = px - cx
        dy = py - cy
        length = math.hypot(dx, dy) or 1.0
        return (px + (dx / length) * distance, py + (dy / length) * distance)

    def _get_current_time_sec(self):
        if not self.player:
            return 0.0
        try:
            return max(0.0, self.player.get_time() / 1000.0)
        except Exception:
            return 0.0

    def _iter_visible_image_items(self):
        time_sec = self._get_current_time_sec()
        for item in self._get_timeline_items():
            if item.type == 'image' and getattr(item, 'visible', True) and item.start_time <= time_sec <= item.end_time:
                yield item

    def _load_overlay_photo(self, item, width, height, draft=False):
        cache_key = (item.id, item.type, int(width), int(height), item.text or '', round(item.opacity, 3), int(item.font_size), item.text_color, round(float(getattr(item, 'rotation', 0.0) or 0.0), 1), bool(draft))
        cached = self._overlay_preview_cache.get(cache_key)
        if cached is not None:
            return cached
        img = self._build_overlay_preview_image(item, width, height, draft=draft)
        if img is None:
            return None
        photo = ImageTk.PhotoImage(img)
        self._invalidate_overlay_preview_cache(item.id)
        self._overlay_preview_cache[cache_key] = photo
        return photo

    def _update_overlay_label(self, item, preview_w, preview_h, draft=False):
        """Render overlay previews.

        ImageOverlay uses the shared transparent overlay canvas so rotated images do not
        expose a per-item rectangular widget surface. Text/subtitle overlays stay on the
        older label path for now.
        """
        viewport_x, viewport_y, _, _ = self._get_video_viewport_rect()
        x, y, w, h = self.overlay_manager.preview_rect(item, preview_w, preview_h)
        photo = self._load_overlay_photo(item, w, h, draft=draft)
        if photo is None:
            return None

        self._overlay_photo_refs[item.id] = photo
        is_selected = item.id == self.overlay_manager.selected_item_id
        is_image = item.type == 'image'
        widget = self._overlay_label_refs.get(item.id)

        if is_image:
            geom = self._get_image_overlay_geometry(item, preview_w, preview_h)
            center_x, center_y = geom['center']
            display_w = max(1, int(photo.width()))
            display_h = max(1, int(photo.height()))

            stale_widget = self._overlay_label_refs.pop(item.id, None)
            if stale_widget is not None and stale_widget.winfo_exists():
                stale_widget.destroy()

            refs = self._overlay_canvas_refs.get(item.id, {})
            for canvas_id in refs.get('markers', []):
                try:
                    self.preview_overlay_canvas.delete(canvas_id)
                except tk.TclError:
                    pass
            old_image_id = refs.get('image')
            if old_image_id:
                try:
                    self.preview_overlay_canvas.delete(old_image_id)
                except tk.TclError:
                    pass

            image_id = self.preview_overlay_canvas.create_image(center_x, center_y, image=photo, anchor='center', tags=('overlay_image', item.id))
            marker_ids = []
            if is_selected:
                color = '#FF9F0A'
                flat = []
                for px, py in geom['corners'] + [geom['corners'][0]]:
                    flat.extend((px, py))
                marker_ids.append(self.preview_overlay_canvas.create_line(*flat, fill=color, width=2, joinstyle=tk.ROUND, tags=('selection_marker', item.id)))
                for px, py in geom['corners']:
                    marker_ids.append(
                        self.preview_overlay_canvas.create_oval(
                            px - 1.5, py - 1.5, px + 1.5, py + 1.5,
                            fill=color, outline='white', width=1, tags=('selection_marker', item.id)
                        )
                    )
            self._overlay_canvas_refs[item.id] = {
                'image': image_id,
                'markers': marker_ids,
                'rect': geom['bbox'],
                'corners': geom['corners'],
                'center': geom['center'],
                'display_size': (display_w, display_h),
            }
            return geom['bbox']

        if widget is None or not widget.winfo_exists() or not isinstance(widget, tk.Label):
            if widget is not None and widget.winfo_exists():
                widget.destroy()
            widget = tk.Label(self.video_frame, bd=0, highlightthickness=0, cursor='fleur')
            widget.bind('<Button-1>', lambda e, item_id=item.id: self.on_overlay_item_press(item_id, e))
            widget.bind('<B1-Motion>', self.on_overlay_drag)
            widget.bind('<ButtonRelease-1>', self.on_overlay_release)
            self._overlay_label_refs[item.id] = widget

        if is_selected:
            widget.configure(image=photo, highlightthickness=2, highlightbackground='#007AFF', highlightcolor='#007AFF', bd=1, relief='solid')
        else:
            widget.configure(image=photo, highlightthickness=0, bd=0, relief='flat')
        widget.image = photo
        display_w = max(1, int(photo.width()))
        display_h = max(1, int(photo.height()))
        center_x = viewport_x + x + (w / 2.0)
        center_y = viewport_y + y + (h / 2.0)
        label_x = int(round(center_x - (display_w / 2.0)))
        label_y = int(round(center_y - (display_h / 2.0)))
        widget.place(x=label_x, y=label_y, width=display_w, height=display_h)
        widget.tk.call('raise', widget._w)
        return (label_x, label_y, display_w, display_h)

    def _position_overlay_handle(self, rect):
        selected = self._get_any_overlay_item(self.overlay_manager.selected_item_id)
        if rect:
            if selected is not None and selected.type == 'image':
                refs = self._overlay_canvas_refs.get(selected.id, {})
                corners = refs.get('corners')
                center = refs.get('center')
                if corners and center:
                    tr = corners[1]
                    br = corners[2]
                    rotate_pt = self._offset_corner_handle(center, tr, 8.0)
                    resize_pt = self._offset_corner_handle(center, br, 5.0)
                    self.overlay_rotate_handle.place(
                        x=max(0, int(round(rotate_pt[0] - 6))),
                        y=max(0, int(round(rotate_pt[1] - 6))),
                        width=12, height=12
                    )
                    self.overlay_rotate_handle.lift()
                    self.overlay_resize_handle.place(
                        x=max(0, int(round(resize_pt[0] - 5))),
                        y=max(0, int(round(resize_pt[1] - 5))),
                        width=10, height=10
                    )
                    self.overlay_resize_handle.lift()
                else:
                    self.overlay_resize_handle.place_forget()
                    self.overlay_rotate_handle.place_forget()
            else:
                x, y, w, h = rect
                self.overlay_resize_handle.place(x=max(0, int(round(x + w - 10))), y=max(0, int(round(y + h - 10))), width=10, height=10)
                self.overlay_resize_handle.lift()
                self.overlay_rotate_handle.place_forget()
        else:
            self.overlay_resize_handle.place_forget()
            self.overlay_rotate_handle.place_forget()

    def _schedule_overlay_prop_refresh(self, delay=80):
        if self._overlay_prop_refresh_job:
            self.root.after_cancel(self._overlay_prop_refresh_job)
        self._overlay_prop_refresh_job = self.root.after(delay, self._flush_overlay_prop_refresh)

    def _flush_overlay_prop_refresh(self):
        self._overlay_prop_refresh_job = None
        self.refresh_overlay_property_panel()

    def _is_overlay_props_widget(self, widget):
        panel = getattr(self, 'overlay_props_inner', None)
        while widget is not None:
            if widget is panel:
                return True
            widget = getattr(widget, 'master', None)
        return False

    def _on_overlay_props_mousewheel(self, event):
        if not hasattr(self, 'overlay_props_canvas') or not self.overlay_props_canvas.winfo_exists():
            return
        if not self._is_overlay_props_widget(getattr(event, 'widget', None)):
            return
        if getattr(event, 'num', None) == 4:
            units = -3
        elif getattr(event, 'num', None) == 5:
            units = 3
        else:
            delta = getattr(event, 'delta', 0)
            if delta == 0:
                return
            units = int(-1 * (delta / 120)) * 3
            if units == 0:
                units = -3 if delta > 0 else 3
        self.overlay_props_canvas.yview_scroll(units, 'units')
        return 'break'

    def _schedule_resize_preview_refresh(self, item_id, delay=40):
        self._overlay_resize_dirty_item = item_id
        if self._overlay_resize_refresh_job:
            return
        self._overlay_resize_refresh_job = self.root.after(delay, self._flush_resize_preview_refresh)

    def _flush_resize_preview_refresh(self):
        self._overlay_resize_refresh_job = None
        item_id = self._overlay_resize_dirty_item
        self._overlay_resize_dirty_item = None
        if not item_id:
            return
        item = self._get_any_overlay_item(item_id)
        if item is None:
            return
        self._invalidate_overlay_preview_cache(item.id)
        preview_w, preview_h = self._get_overlay_preview_size()
        rect = self._update_overlay_label(item, preview_w, preview_h, draft=False)
        if item.id == self.overlay_manager.selected_item_id:
            self._position_overlay_handle(rect)

    def _compute_overlay_visible_signature(self, time_sec):
        items = [
            item for item in self._get_timeline_items()
            if item.visible and item.start_time <= time_sec <= item.end_time
        ]
        return tuple((item.id, item.layer_index) for item in items if item.type in ('image', 'text', 'subtitle'))

    def _refresh_overlay_time_state(self, time_sec):
        if self._overlay_drag.get('item_id') and self._overlay_drag.get('mode') == 'resize':
            return
        signature = self._compute_overlay_visible_signature(time_sec)
        if signature != self._overlay_last_visible_signature:
            self.refresh_overlay_preview(time_sec)

    def refresh_overlay_preview(self, time_sec=None):
        if not hasattr(self, 'preview_overlay_canvas'):
            return
        self._update_overlay_layer_window()
        self._overlay_photo_refs = {}
        self._overlay_canvas_refs = {}
        try:
            self.preview_overlay_canvas.delete('all')
        except tk.TclError:
            pass
        preview_w, preview_h = self._get_overlay_preview_size()
        now = self._get_overlay_time() if time_sec is None else time_sec
        self._overlay_last_visible_signature = self._compute_overlay_visible_signature(now)
        visible_items = [item for item in self._get_timeline_items() if item.visible and item.start_time <= now <= item.end_time]
        visible_ids = set()
        selected_id = self.overlay_manager.selected_item_id
        selected_rect = None
        visible_image = False
        for item in visible_items:
            if item.type not in ('image', 'text', 'subtitle'):
                continue
            visible_ids.add(item.id)
            rect = self._update_overlay_label(item, preview_w, preview_h, draft=False)
            if item.type == 'image':
                visible_image = True
            if item.id == selected_id:
                selected_rect = rect
        for item_id, label in list(self._overlay_label_refs.items()):
            if item_id not in visible_ids and label.winfo_exists():
                label.place_forget()
        if visible_image:
            self._update_overlay_layer_window()
        else:
            try:
                self.preview_overlay_window.withdraw()
            except tk.TclError:
                pass
        self._position_overlay_handle(selected_rect if selected_id in visible_ids else None)

    def _get_overlay_timeline_total_duration(self):
        total_duration = 1.0
        if self.player and self.player.get_length() > 0:
            total_duration = max(total_duration, self.player.get_length() / 1000.0)
        for item in self._get_timeline_items():
            total_duration = max(total_duration, item.end_time)
        return total_duration

    def _get_timeline_zoom_factor(self):
        raw = getattr(self, 'overlay_zoom_var', None)
        raw = raw.get() if raw else '1x'
        try:
            return max(1.0, float(str(raw).rstrip('xX')))
        except Exception:
            return 1.0

    def _get_overlay_timeline_content_width(self, base_width=None):
        if base_width is None:
            base_width = max(400, self.overlay_timeline_canvas.winfo_width())
        return max(base_width, int(base_width * self._get_timeline_zoom_factor()))

    def _time_to_timeline_x(self, time_sec, total_duration=None, width=None):
        if total_duration is None:
            total_duration = self._get_overlay_timeline_total_duration()
        if width is None:
            width = self._get_overlay_timeline_content_width()
        span = max(1, width - 130)
        return 110 + (max(0.0, min(total_duration, time_sec)) / max(total_duration, 0.001)) * span

    def _timeline_x_to_time(self, x, total_duration=None, width=None):
        if total_duration is None:
            total_duration = self._get_overlay_timeline_total_duration()
        if width is None:
            width = self._get_overlay_timeline_content_width()
        span = max(1, width - 130)
        return max(0.0, min(total_duration, ((x - 110) / span) * total_duration))

    def _get_timeline_snap_seconds(self):
        mode = getattr(self, 'overlay_snap_var', None)
        mode = mode.get() if mode else '끄기'
        if mode == '0.1초':
            return 0.1
        if mode == '프레임':
            fps = float(getattr(self, '_timeline_fps', 30.0) or 30.0)
            return 1.0 / max(1.0, fps)
        return None

    def _snap_timeline_time(self, value):
        step = self._get_timeline_snap_seconds()
        if not step:
            return max(0.0, value)
        return max(0.0, round(value / step) * step)

    def _get_timeline_ruler_step(self, total_duration=None, width=None):
        if total_duration is None:
            total_duration = self._get_overlay_timeline_total_duration()
        if width is None:
            width = self._get_overlay_timeline_content_width()
        span = max(1, width - 130)
        target_px = 90
        candidates = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 30.0, 60.0]
        for step in candidates:
            px = (step / max(total_duration, 0.001)) * span
            if px >= target_px:
                return step
        return candidates[-1]

    def _draw_overlay_timeline_ruler(self, total_duration, width, ruler_h=24):
        canvas = self.overlay_timeline_canvas
        step = self._get_timeline_ruler_step(total_duration, width)
        t = 0.0
        while t <= total_duration + (step * 0.5):
            x = self._time_to_timeline_x(t, total_duration, width)
            canvas.create_line(x, 4, x, ruler_h, fill=self.C['border'], tags=('timeline_ruler',))
            canvas.create_text(x + 2, 2, text=f'{t:.1f}', anchor='nw', fill=self.C['text2'], font=('Noto Sans KR', 9), tags=('timeline_ruler',))
            t += step
        canvas.create_line(110, ruler_h, width - 10, ruler_h, fill=self.C['border'], tags=('timeline_ruler',))

    def _hit_overlay_timeline_items(self, x, y):
        hits = []
        for item_id, info in reversed(list(self._overlay_timeline_regions.items())):
            x1, y1, x2, y2 = info['rect']
            if x1 <= x <= x2 and y1 <= y <= y2:
                edge = 8
                if abs(x - x1) <= edge:
                    mode = 'trim_start'
                elif abs(x - x2) <= edge:
                    mode = 'trim_end'
                else:
                    mode = 'move'
                hits.append((item_id, mode))
        return hits

    def _pick_overlay_timeline_hit(self, hits, x, y, advance=False):
        if not hits:
            self._overlay_timeline_cycle = {'key': None, 'index': 0, 'items': []}
            return None, None
        cycle_key = (round(x / 6), round(y / 6), tuple(hit[0] for hit in hits))
        cycle = getattr(self, '_overlay_timeline_cycle', {'key': None, 'index': 0, 'items': []})
        if cycle.get('key') != cycle_key:
            cycle = {'key': cycle_key, 'index': 0, 'items': hits[:]}
        elif advance:
            cycle['index'] = (cycle.get('index', 0) + 1) % len(hits)
            cycle['items'] = hits[:]
        self._overlay_timeline_cycle = cycle
        return cycle['items'][cycle['index']]

    def refresh_overlay_timeline(self):
        if not hasattr(self, 'overlay_timeline_canvas'):
            return
        canvas = self.overlay_timeline_canvas
        canvas.delete('all')
        self._overlay_timeline_regions = {}
        visible_width = max(400, canvas.winfo_width())
        width = self._get_overlay_timeline_content_width(visible_width)
        row_h = 34
        ruler_h = 24
        top_pad = 10
        total_duration = self._get_overlay_timeline_total_duration()
        track_specs = [(idx, track.name, sorted(track.items, key=lambda ov: (ov.layer_index, ov.id))) for idx, track in enumerate(self.overlay_manager.tracks)]
        subtitle_items = self._get_subtitle_adapter_items()
        if subtitle_items:
            track_specs.append((len(track_specs), '자막 어댑터', subtitle_items))
        self._draw_overlay_timeline_ruler(total_duration, width, ruler_h)
        for track_idx, track_name, track_items in track_specs:
            y1 = top_pad + ruler_h + track_idx * row_h
            y2 = y1 + 24
            canvas.create_text(10, y1 + 12, text=track_name, anchor='w', fill=self.C['text2'], font=('Noto Sans KR', 10))
            for item in track_items:
                x1 = self._time_to_timeline_x(item.start_time, total_duration, width)
                x2 = self._time_to_timeline_x(item.end_time, total_duration, width)
                x2 = max(x1 + 18, x2)
                is_selected = item.id == self.overlay_manager.selected_item_id
                fill = '#0A84FF' if is_selected else ('#5AC8FA' if item.visible else '#8E8E93')
                outline = '#FFFFFF' if is_selected else ''
                canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=1, tags=(item.id, 'overlay_item'))
                if item.type == 'text':
                    tag_name = 'TXT'
                elif item.type == 'subtitle':
                    tag_name = 'SUB'
                else:
                    tag_name = 'IMG'
                label = f'{tag_name} {item.layer_index}' if item.visible else f'{tag_name} {item.layer_index} OFF'
                text_fill = 'white' if item.visible else '#E5E5EA'
                canvas.create_text(x1 + 6, y1 + 12, text=label, anchor='w', fill=text_fill, font=('Noto Sans KR', 9, 'bold'), tags=(item.id, 'overlay_item'))
                self._overlay_timeline_regions[item.id] = {'rect': (x1, y1, x2, y2), 'track_index': track_idx}
        total_tracks = max(1, len(track_specs))
        scroll_h = 6 if getattr(self, 'overlay_timeline_hscroll', None) and self.overlay_timeline_hscroll.winfo_exists() else 0
        bottom = top_pad + ruler_h + total_tracks * row_h + 12 + scroll_h
        canvas.configure(scrollregion=(0, 0, width, bottom))
        self._update_overlay_timeline_playhead(total_duration, width, row_h, ruler_h, top_pad, total_tracks)

    def _update_overlay_timeline_playhead(self, total_duration=None, width=None, row_h=34, ruler_h=24, top_pad=10, total_tracks=None):
        if not hasattr(self, 'overlay_timeline_canvas'):
            return
        canvas = self.overlay_timeline_canvas
        if width is None:
            width = self._get_overlay_timeline_content_width()
        if total_duration is None:
            total_duration = 1.0
            if self.player and self.player.get_length() > 0:
                total_duration = max(total_duration, self.player.get_length() / 1000.0)
            for item in self._get_timeline_items():
                total_duration = max(total_duration, item.end_time)
        if total_tracks is None:
            total_tracks = max(1, len(self.overlay_manager.tracks) + (1 if self._get_subtitle_adapter_items() else 0))
        current_sec = self._get_overlay_time()
        x = self._time_to_timeline_x(current_sec, total_duration, width)
        y1 = 4
        y2 = top_pad + ruler_h + total_tracks * row_h + 6
        if self._overlay_timeline_playhead and canvas.type(self._overlay_timeline_playhead):
            canvas.coords(self._overlay_timeline_playhead, x, y1, x, y2)
            canvas.itemconfigure(self._overlay_timeline_playhead, fill='#FF453A', width=2)
        else:
            self._overlay_timeline_playhead = canvas.create_line(x, y1, x, y2, fill='#FF453A', width=2)

    def on_overlay_timeline_press(self, event):
        canvas_x = self.overlay_timeline_canvas.canvasx(event.x)
        shift_pressed = bool(event.state & 0x0001)
        hits = self._hit_overlay_timeline_items(canvas_x, event.y)
        item_id, mode = self._pick_overlay_timeline_hit(hits, canvas_x, event.y, advance=shift_pressed or len(hits) > 1)
        if not item_id:
            return
        item = self._get_any_overlay_item(item_id)
        if item is None:
            return
        self.overlay_manager.set_selected(item_id)
        press_time = self._timeline_x_to_time(canvas_x)
        self._overlay_timeline_drag = {
            'item_id': item_id,
            'mode': mode,
            'press_time': press_time,
            'origin_start': item.start_time,
            'origin_end': item.end_time,
        }
        self.refresh_overlay_preview()
        self.refresh_overlay_timeline()
        self.refresh_overlay_property_panel()

    def on_overlay_timeline_drag(self, event):
        item_id = self._overlay_timeline_drag.get('item_id')
        if not item_id:
            return
        item = self._get_any_overlay_item(item_id)
        if item is None:
            return
        mode = self._overlay_timeline_drag.get('mode')
        current_time = self._timeline_x_to_time(self.overlay_timeline_canvas.canvasx(event.x))
        min_len = 0.05
        if mode == 'move':
            raw_delta = current_time - self._overlay_timeline_drag['press_time']
            duration = self._overlay_timeline_drag['origin_end'] - self._overlay_timeline_drag['origin_start']
            new_start = self._snap_timeline_time(self._overlay_timeline_drag['origin_start'] + raw_delta)
            new_end = self._snap_timeline_time(new_start + duration)
            if new_start < 0:
                new_start = 0.0
                new_end = self._snap_timeline_time(new_start + duration)
            self._apply_item_timeline_times(item, new_start, max(new_start + min_len, new_end))
        elif mode == 'trim_start':
            new_start = self._snap_timeline_time(current_time)
            self._apply_item_timeline_times(item, min(max(0.0, new_start), item.end_time - min_len), item.end_time)
        elif mode == 'trim_end':
            new_end = self._snap_timeline_time(current_time)
            self._apply_item_timeline_times(item, item.start_time, max(item.start_time + min_len, new_end))
        self.refresh_overlay_preview()
        self.refresh_overlay_timeline()
        self.refresh_overlay_property_panel()

    def on_overlay_timeline_release(self, event):
        if self._overlay_timeline_drag.get('item_id'):
            self.refresh_overlay_preview()
            self.refresh_overlay_timeline()
            self.refresh_overlay_property_panel()
        self._overlay_timeline_drag = {'item_id': None, 'mode': None, 'press_time': 0.0, 'origin_start': 0.0, 'origin_end': 0.0}

    def _find_overlay_hit(self, x, y):
        selected = self.overlay_manager.get_selected()
        if selected is not None and selected.type == 'image':
            refs = self._overlay_canvas_refs.get(selected.id)
            if refs and refs.get('corners'):
                corners = refs['corners']
                center = refs.get('center')
                if self._point_in_polygon(x, y, corners):
                    if center and self._distance_sq((x, y), corners[2]) <= (12 * 12):
                        return 'resize', selected.id
                    return 'move', selected.id

        visible_images = sorted(
            (item for item in self._iter_visible_image_items()),
            key=lambda ov: (ov.track_index, ov.layer_index),
            reverse=True,
        )
        for item in visible_images:
            refs = self._overlay_canvas_refs.get(item.id)
            if not refs or not refs.get('corners'):
                continue
            corners = refs['corners']
            center = refs.get('center')
            if not self._point_in_polygon(x, y, corners):
                continue
            if center and self._distance_sq((x, y), corners[2]) <= (12 * 12):
                return 'resize', item.id
            return 'move', item.id
        return None, None

    def on_overlay_rotate_press(self, event):
        selected = self.overlay_manager.get_selected()
        if selected is None or selected.type != 'image':
            return
        refs = self._overlay_canvas_refs.get(selected.id)
        if refs and refs.get('center'):
            cx, cy = refs['center']
        else:
            preview_w, preview_h = self._get_overlay_preview_size()
            geom = self._get_image_overlay_geometry(selected, preview_w, preview_h)
            cx, cy = geom['center']
        layer_x, layer_y, _, _ = self._get_overlay_layer_geometry()
        cx = layer_x + cx
        cy = layer_y + cy
        start_angle = math.degrees(math.atan2(event.y_root - cy, event.x_root - cx))
        self._overlay_drag = {
            'item_id': selected.id,
            'mode': 'rotate',
            'start_x': event.x_root,
            'start_y': event.y_root,
            'origin': (selected.x, selected.y, selected.width, selected.height),
            'origin_rotation': float(selected.rotation or 0.0),
            'center_root': (cx, cy),
            'start_angle': start_angle,
        }

    def on_overlay_handle_press(self, event):
        selected = self.overlay_manager.get_selected()
        if selected is None:
            return
        self._overlay_drag = {
            'item_id': selected.id,
            'mode': 'resize',
            'start_x': event.x_root,
            'start_y': event.y_root,
            'origin': (selected.x, selected.y, selected.width, selected.height),
        }

    def on_overlay_item_press(self, item_id, event):
        item = self._get_any_overlay_item(item_id)
        if item is None:
            return
        self.overlay_manager.set_selected(item_id)
        self._overlay_drag = {
            'item_id': item_id,
            'mode': 'move',
            'start_x': event.x_root,
            'start_y': event.y_root,
            'origin': (item.x, item.y, item.width, item.height),
        }
        self.refresh_overlay_preview()
        self.refresh_overlay_timeline()
        self.refresh_overlay_property_panel()

    def on_overlay_press(self, event):
        mode, item_id = self._find_overlay_hit(event.x, event.y)
        if not item_id:
            self.overlay_manager.set_selected(None)
            self.refresh_overlay_preview()
            self.refresh_overlay_property_panel()
            return
        item = self._get_any_overlay_item(item_id)
        if item is None:
            return
        self.overlay_manager.set_selected(item_id)
        self._overlay_drag = {
            'item_id': item_id,
            'mode': mode,
            'start_x': event.x_root,
            'start_y': event.y_root,
            'origin': (item.x, item.y, item.width, item.height),
        }
        self.refresh_overlay_preview()
        self.refresh_overlay_timeline()
        self.refresh_overlay_property_panel()

    def on_overlay_drag(self, event):
        item_id = self._overlay_drag.get('item_id')
        if not item_id:
            return
        item = self._get_any_overlay_item(item_id)
        if item is None:
            return
        preview_w, preview_h = self._get_overlay_preview_size()
        px, py, pw, ph = self.overlay_manager.preview_rect(item, preview_w, preview_h)
        dx = event.x_root - self._overlay_drag['start_x']
        dy = event.y_root - self._overlay_drag['start_y']
        if self._overlay_drag['mode'] == 'rotate':
            cx, cy = self._overlay_drag['center_root']
            current_angle = math.degrees(math.atan2(event.y_root - cy, event.x_root - cx))
            item.rotation = self._overlay_drag['origin_rotation'] + (current_angle - self._overlay_drag['start_angle'])
            self._invalidate_overlay_preview_cache(item.id)
            rect = self._update_overlay_label(item, preview_w, preview_h, draft=False)
            if item.id == self.overlay_manager.selected_item_id:
                self._position_overlay_handle(rect)
            self._schedule_overlay_prop_refresh()
            return
        if self._overlay_drag['mode'] == 'resize':
            new_x, new_y = px, py
            new_w = max(24, pw + dx)
            new_h = max(24, ph + dy)
        else:
            new_x = max(0, px + dx)
            new_y = max(0, py + dy)
            new_w, new_h = pw, ph
        self.overlay_manager.update_item_from_preview_rect(item, new_x, new_y, new_w, new_h, preview_w, preview_h)
        self._overlay_drag['start_x'] = event.x_root
        self._overlay_drag['start_y'] = event.y_root
        if self._overlay_drag['mode'] == 'resize':
            self._invalidate_overlay_preview_cache(item.id)
            rect = self._update_overlay_label(item, preview_w, preview_h, draft=True)
            if item.id == self.overlay_manager.selected_item_id:
                self._position_overlay_handle(rect)
            self._schedule_resize_preview_refresh(item.id)
            self._schedule_overlay_prop_refresh()
        else:
            rect = self._update_overlay_label(item, preview_w, preview_h, draft=False)
            if item.id == self.overlay_manager.selected_item_id:
                self._position_overlay_handle(rect)
            self._schedule_overlay_prop_refresh()

    def on_overlay_release(self, event):
        if self._overlay_drag.get('item_id'):
            if self._overlay_resize_refresh_job:
                self.root.after_cancel(self._overlay_resize_refresh_job)
                self._overlay_resize_refresh_job = None
            if self._overlay_prop_refresh_job:
                self.root.after_cancel(self._overlay_prop_refresh_job)
                self._overlay_prop_refresh_job = None
            self.refresh_overlay_preview()
            self.refresh_overlay_timeline()
            self.refresh_overlay_property_panel()
        self._overlay_drag = {'item_id': None, 'mode': None, 'start_x': 0, 'start_y': 0, 'origin': None}

    def apply_vlc_sub_settings(self):
        """[ASS ?レ뒪?? ?붿옄??蹂寃???ASS ?뚯씪留??ъ깮?깊븯??VLC??利됱떆 濡쒕뱶"""
        self.apply_preview_subtitles(force_reload=False)

    def on_select_video(self):
        p = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov *.flv")])
        if p:
            self.current_video_path = p
            
            # 湲곗〈??濡쒕뱶???먮쭑 ?뚯씪 ?곌껐 ?딄린
            if hasattr(self, 'preview_srt_path'):
                self.preview_srt_path = None
                
            if self.player.load_video(p):
                self.reset_for_new_video()
                try:
                    self._timeline_fps = float(self.video_editor.get_media_info(p).get('fps', 30.0) or 30.0)
                except Exception:
                    self._timeline_fps = 30.0
                def _resize():
                    w, h = self.player.get_video_resolution()
                    if w > 0 and h > 0:
                        self._video_aspect = h / w
                        self.overlay_manager.render_width = w
                        self.overlay_manager.render_height = h
                        self.refresh_overlay_preview()
                    self.video_canvas.pack_propagate(False)
                self.root.after(500, _resize)
                
                self.lbl_status.config(text='영상 로드됨: ' + os.path.basename(p), fg=self.C['accent'])
                self.reset_action_button()
                
                if hasattr(self, 'preview_srt_path') and getattr(self, 'preview_srt_path') and os.path.exists(self.preview_srt_path):
                    self.root.after(300, self.apply_preview_subtitles)
            else:
                from tkinter import messagebox
                messagebox.showerror('오류', '영상을 먼저 불러와 주세요.')


    def on_stop_action(self):
        if self.stop_event and not self.stop_event.is_set():
            self.stop_event.set()
        self.lbl_status.config(text='진행 중인 작업을 중지하는 중...', fg=self.C['red'])
        self.btn_stop.configure(state=tk.DISABLED)
        self.root.after(1500, lambda: self.reset_action_button() or self.lbl_status.config(text='작업이 중지되었습니다.', fg=self.C['red']))


    def on_start_analysis(self):
        mode = self.mode_var.get()
        selected_model = self.ai_model_var.get().split(" ")[0]
        self.engine.set_model_id(selected_model)
        
        # [??뺣빍???곕떽?] ?브쑴苑???????륁춿
        try: min_sil_ms, pad_ms = int(self.silence_dur_var.get() * 1000), int(self.speech_pad_var.get() * 1000)
        except: min_sil_ms, pad_ms = 2000, 250
        
        device_val = self.device_var.get()
        if "auto" in device_val: mapped_dev = "auto"
        elif "cuda" in device_val: mapped_dev = "cuda"
        elif "mps" in device_val: mapped_dev = "mps"
        elif "25%" in device_val: mapped_dev = "cpu_25"
        elif "50%" in device_val: mapped_dev = "cpu_50"
        elif "75%" in device_val: mapped_dev = "cpu_75"
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
            use_whisperx_align=getattr(self, 'use_whisperx_var', tk.BooleanVar(value=False)).get(),
            remove_punctuation=getattr(self, 'remove_punctuation_var', tk.BooleanVar(value=False)).get(),
            device_mode=mapped_dev
        )
        
        self.stop_event = threading.Event(); self.btn_analyze.configure(state=tk.DISABLED); self.btn_stop.configure(state=tk.NORMAL); self.progress_var.set(0); self.results_data = []
        for i in self.tree.get_children(): self.tree.delete(i)
        
        # ?뚢뫂?껅에?살쑎???臾믩씜 ???
        max_chars = self.max_len_int.get()
        threading.Thread(target=self.controller.run_analysis, args=(self.current_video_path, self.stop_event, mode, min_sil_ms, pad_ms, max_chars, analysis_options), daemon=True).start()

    def _collect_overlays_for_export(self):
        overlays = []
        for item in self._get_timeline_items():
            if not item.visible:
                continue
            if item.type == 'image':
                if not item.source:
                    continue
                overlays.append({
                    'type': 'image',
                    'source': item.source,
                    'start_time': item.start_time,
                    'end_time': item.end_time,
                    'x': item.x,
                    'y': item.y,
                    'width': item.width,
                    'height': item.height,
                    'rotation': item.rotation,
                    'opacity': item.opacity,
                    'track_index': item.track_index,
                    'layer_index': item.layer_index,
                })
            elif item.type in ('text', 'subtitle'):
                overlays.append({
                    'type': item.type,
                    'text': item.text or '',
                    'start_time': item.start_time,
                    'end_time': item.end_time,
                    'x': item.x,
                    'y': item.y,
                    'width': item.width,
                    'height': item.height,
                    'opacity': item.opacity,
                    'font_size': item.font_size,
                    'text_color': item.text_color,
                    'track_index': item.track_index,
                    'layer_index': item.layer_index,
                })
        overlays.sort(key=lambda ov: (ov.get('track_index', 0), ov.get('layer_index', 0)))
        return overlays

    def start_export(self, fast=True):
        media_info = self.video_editor.get_media_info(self.current_video_path); ext = os.path.splitext(self.current_video_path)[1].lower().strip('.')
        save_path = filedialog.asksaveasfilename(defaultextension=f".{ext if ext in ['mp4','mkv','mov','avi'] else 'mp4'}", filetypes=[("Video File", f"*.{ext}")], initialfile=f"cut_{os.path.basename(self.current_video_path)}")
        if save_path:
            for b in [self.btn_fast_save, self.btn_pro_save]: b.configure(state=tk.DISABLED)
            self.btn_stop.configure(state=tk.NORMAL); self.progress_var.set(0)
            
            # burn ??? ASS ?? ??
            ass_path_final = None
            if self.use_burn_sub_var.get():
                try:
                    merged, _ = self.video_editor.get_merged_segments_info(self.results_data)

                    def hex_to_ass(hex_color):
                        hex_color = hex_color.lstrip('#')
                        r = int(hex_color[0:2], 16)
                        g = int(hex_color[2:4], 16)
                        b = int(hex_color[4:6], 16)
                        return f"&H00{b:02X}{g:02X}{r:02X}&"

                    font_name = self.sub_font.get() if hasattr(self, 'sub_font') else '留묒? 怨좊뵓'
                    font_size = self.sub_font_size.get() if hasattr(self, 'sub_font_size') else 40
                    ass_primary = hex_to_ass(self.sub_color_f.get() if hasattr(self, 'sub_color_f') else '#ffffff')
                    ass_outline = hex_to_ass(self.sub_color_o.get() if hasattr(self, 'sub_color_o') else '#000000')
                    ass_shadow = hex_to_ass(self.sub_color_s.get() if hasattr(self, 'sub_color_s') else '#000000')
                    outline_w = self.sub_outline.get() if hasattr(self, 'sub_outline') else 3
                    shadow_w = self.sub_shadow.get() if hasattr(self, 'sub_shadow') else 3
                    margin_v = self.sub_y_pos.get() if hasattr(self, 'sub_y_pos') else 50

                    ass_header = f'''[Script Info]
Title: Export
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
'''

                    def fmt_ass_time(sec):
                        h = int(sec // 3600)
                        m = int((sec % 3600) // 60)
                        s = int(sec % 60)
                        cs = int((sec % 1) * 100)
                        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

                    # ?? ?? ??? filler ??
                    _FILLERS = {'?', '?', '?', '??', '?', '??', '?', '?', '?'}

                    def _get_display_start(r):
                        words = r.get('words', [])
                        if not words:
                            return r['s']
                        for w in words:
                            wt = w['word'].strip() if isinstance(w, dict) else w.word.strip()
                            wclean = wt.replace(' ', '').replace('.', '').replace(',', '').replace('-', '').replace('~', '')
                            if not wclean:
                                continue
                            if wclean in _FILLERS or (len(wclean) <= 3 and len(set(wclean)) <= 1):
                                continue
                            ws = w['s'] if isinstance(w, dict) else w.s
                            if ws - r['s'] > 1.5:
                                return r['s']
                            return ws
                        return r['s']

                    lines = []
                    current_out_time = 0.0
                    for m_start, m_end in merged:
                        for r in self.results_data:
                            if r['s'] >= m_start - 0.001 and r['e'] <= m_end + 0.001:
                                rel_s = _get_display_start(r) - m_start
                                rel_e = r['e'] - m_start
                                s_out = current_out_time + rel_s
                                e_out = current_out_time + rel_e
                                lines.append(f"Dialogue: 0,{fmt_ass_time(s_out)},{fmt_ass_time(e_out)},Default,,0,0,0,,{r['t']}")
                        current_out_time += (m_end - m_start)

                    ass_path_final = os.path.join(self.base_dir, f"export_burn_{int(time.time())}.ass")
                    with open(ass_path_final, 'w', encoding='utf-8-sig') as f:
                        f.write(ass_header); f.write('\n'.join(lines))
                except Exception as e:
                    print(f"[Error] Burn ASS Generation failed: {e}")
            
            overlays = self._collect_overlays_for_export()
            settings = {'v_codec': media_info.get('v_codec', 'h264'), 'a_codec': media_info.get('a_codec', 'aac'), 'v_bitrate': f"{media_info.get('v_bitrate', 5000000) // 1000}k", 'a_bitrate': f"{media_info.get('a_bitrate', 128000) // 1000}k", 'fast_mode': fast, 'overlays': overlays}
            threading.Thread(target=self.controller.run_editing, args=(self.current_video_path, save_path, self.results_data, self.stop_event, settings, ass_path_final), daemon=True).start()

    def on_export_xml(self):
        save_path = filedialog.asksaveasfilename(defaultextension=".xml", filetypes=[("Final Cut Pro XML", "*.xml")], initialfile=f"Timeline_{os.path.splitext(os.path.basename(self.current_video_path))[0]}.xml")
        if save_path:
            try:
                media_info = self.video_editor.get_media_info(self.current_video_path); real_fps = media_info.get("fps", 30.0)
                if self.video_editor.export_premiere_xml(self.current_video_path, self.results_data, save_path, fps=real_fps): messagebox.showinfo('완료', f'XML 내보내기가 완료되었습니다.\n{save_path}')
                else: messagebox.showerror('오류', 'XML 내보내기에 실패했습니다.')
            except Exception as e: messagebox.showerror('오류', str(e))



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
                    # ??뽰삂 ??볦퍢 ????#2) vs ?ル굝利???볦퍢 ????#3) ?브쑨由?筌ｌ꼶??
                    if col == '#3': t_sec = self.parse_time(val[2])
                    else: t_sec = self.parse_time(val[1])
                    self.player.set_time(int(t_sec * 1000))
                except Exception as e: print(f'[WARN] ?紐꺿봺 ??????볦퍢 ??猷???살첒: {e}')
            
    def edit_selected_text(self):
        sel = self.tree.selection()
        if not sel: return
        item = sel[0]
        bbox = self.tree.bbox(item, '#4')
        if bbox:
            x, y, w, h = bbox
            self._open_editor(item, x, y, max(w, 200), max(h, 20))


    def rebuild_tree_and_render(self, fast=False):
        # [??뺣빍??筌ㅼ뮇??? Treeview 揶쏄퉮??? ?겸뫖?????쥓?ㅿ쭪?筌? Canvas ?袁⑷퍥 ????遺얠춦?? ?얜떯苡??щ빍??
        # Ctrl+??鈺곌퀣????뽯퓠??fast=True????띻볼 Treeview筌?揶쏄퉮???몃빍??
        
        # ?袁⑹삺 ?醫뤾문???袁⑹뵠??疫꿸퀣堉?(??쎄쾿嚥??醫????袁る맙)
        selected_idx = -1
        sel = self.tree.selection()
        if sel:
            val = self.tree.item(sel[0])['values']
            if val: selected_idx = int(val[0]) - 1

        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self.results_data):
            self.tree.insert("", "end", values=(i+1, self.format_time(r.get('s',0)), self.format_time(r.get('e',0)), r.get('t','')))
        
        # ?醫뤾문 ?怨밴묶 癰귣벀??
        if selected_idx != -1:
            for item in self.tree.get_children():
                if int(self.tree.item(item)['values'][0]) - 1 == selected_idx:
                    self.tree.selection_set(item)
                    break

        if not fast:
            # [??????遺욧퍕] ??λ선 ?됰뗀以???0甕??????춸 筌띾뜄苡울쭪?筌?뗀苡???귐뗫늄??됰뻻 ??묐뻬 (?源낅뮟 ??됰튋)
            if getattr(self, "notebook", None) and self.notebook.index(self.notebook.select()) == 0:
                self.block_editor.render_block_view()
        
        self.apply_preview_subtitles(force_reload=True)



    def _open_editor(self, item, x, y, w, h, click_x=None):
        val = self.tree.item(item).get('values')
        if not val: return
        target_idx = int(val[0]) - 1
        text = str(val[3] if len(val) > 3 else "")
        entry = tk.Entry(self.tree)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, text)
        entry.focus()

        # [??뺣빍??筌ㅼ뮇??? ????癒? ?????x ?ル슦紐당몴??④쑴沅??뤿연 ????疫꼲????????뚣끉苑???곌때
        if click_x is not None:
            def _set_cursor():
                idx = entry.index(f"@{max(0, click_x)}")
                entry.icursor(idx)
            self.root.after(10, _set_cursor)
        else:
            entry.selection_range(0, tk.END)

        # [??뺣빍??筌뤴뫁???紐껋삋?? ??쎄쾿嚥?????용뮞????낆젾筌≪럩???癒?궚 ?? ?袁⑺뒄????쇰뻻揶쏄쑴?앮에??怨뺤뵬揶쎛?袁⑥쨯 ?곕뗄??
        def _track_position():
            if not entry.winfo_exists(): return
            if not self.tree.exists(item):
                entry.place(x=-9999, y=-9999)
            else:
                bbox = self.tree.bbox(item, '#4')
                if bbox:
                    nx, ny, nw, nh = bbox
                    entry.place(x=nx, y=ny, width=max(nw, 200), height=max(nh, 20))
                else:
                    entry.place(x=-9999, y=-9999) # ?遺얇늺 獄쏅쉼?앮에???쎄쾿嚥????袁⑸뻻 ??? 筌ｌ꼶??
            self.root.after(15, _track_position)
        
        _track_position()

        # [??뺣빍??筌ㅼ뮇??? ??쇰뻻揶?????꾨릅 獄쏆꼷??(Debounced)
        def _on_key_release(event):
            if event.keysym in ['Return', 'Escape']: return
            if hasattr(self, '_edit_debounce_timer') and self._edit_debounce_timer:
                self.root.after_cancel(self._edit_debounce_timer)
            self._edit_debounce_timer = self.root.after(300, save_edit_live)

        def save_edit_live():
            if not entry.winfo_exists(): return
            new_text = entry.get()
            
            if not (0 <= target_idx < len(self.results_data)): return
            old_text = self.results_data[target_idx].get('t', "")
            
            if old_text != new_text:
                self.transcript_manager.save_state()
                self.results_data[target_idx]['t'] = new_text
                # [??뺣빍??筌ㅼ뮇??? ??용뮞????륁젟 獄쏆뮇源???疫꿸퀣????λ선 ?됰뗀以?獄쏄퀣肉? ???뇵?????퉸 ?? 筌욊쑴?????癒?짗 ?브쑵釉???????醫딅즲
                self.results_data[target_idx].pop('words', None)
                self.apply_preview_subtitles(force_reload=True)
            
            if self.tree.exists(item):
                self.tree.set(item, column='#4', value=new_text)

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
        """ASS ??? ?? ??? ???? VLC? ?? ????."""
        if not self.results_data or not self.player: return
        try:
            # HEX(#RRGGBB) -> ASS(&H00BBGGRR&) ??
            def hex_to_ass(hex_color):
                hex_color = hex_color.lstrip('#')
                r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
                return f"&H00{b:02X}{g:02X}{r:02X}&"
            
            # ?? UI ??? ??
            font_name = getattr(self, 'sub_font', None)
            font_name = font_name.get() if font_name else '?? ??'
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
            
            # --- ASS ??삳쐭 ?臾믨쉐 ---
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
            # --- ASS ??볦퍢 ????H:MM:SS.cs ---
            def fmt_ass_time(sec):
                h = int(sec // 3600)
                m = int((sec % 3600) // 60)
                s = int(sec % 60)
                cs = int((sec % 1) * 100)
                return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
            
            _FILLERS = {'?', '?', '?', '??', '?', '??', '?', '?', '?'}

            def _get_display_start(r):
                """Return a stable display start time for preview/export."""
                words = r.get('words', [])
                if not words:
                    return r['s']
                for w in words:
                    # words? dict ?? dataclass ?? ?? ??
                    wt = w['word'].strip() if isinstance(w, dict) else w.word.strip()
                    # Whisper filler ??? ?? ???? ??
                    wclean = wt.replace(' ', '').replace('.', '').replace(',', '').replace('-', '').replace('~', '')
                    if not wclean: continue
                    
                    # ?袁⑥쑎 ??λ선??욧탢??1~3疫꼲??獄쏆꼶????곷선, ??곷선????????椰꾨?瑗??
                    if wclean in _FILLERS or (len(wclean) <= 3 and len(set(wclean)) <= 1):
                        continue
                        
                    ws = w['s'] if isinstance(w, dict) else w.s
                    # ?硫몃젃?믪눛????뽰삂癰귣???1.5????곴맒 ???앾쭖??癒?궚 ?醫? (??댭???苡???ㅻ뮉 野?獄쎻뫗?)
                    if ws - r['s'] > 1.5:
                        return r['s']
                    return ws
                return r['s']

            lines = []
            for i, r in enumerate(self.results_data):
                s_r = _get_display_start(r)  # ??쇱젫 ??λ선 疫꿸퀣? ??뽯뻻 ??뽰삂??
                e_r = r['e']
                if i < len(self.results_data) - 1 and e_r >= self.results_data[i+1]['s']:
                    e_r = max(s_r + 0.1, self.results_data[i+1]['s'] - 0.05)
                lines.append(f"Dialogue: 0,{fmt_ass_time(s_r)},{fmt_ass_time(e_r)},Default,,0,0,0,,{r['t']}")
            
            # --- A/B ?臾볥렜 ??щ뮞??---
            suffix = "A" if getattr(self, '_ping_pong', False) else "B"
            self._ping_pong = not getattr(self, '_ping_pong', False)
            _script_dir = self.base_dir
            ass_name = os.path.join(_script_dir, f"temp_preview_{suffix}.ass")
            
            with open(ass_name, 'w', encoding='utf-8-sig') as f:
                f.write(ass_header)
                f.write('\n'.join(lines))
                f.write('\n')
            
            self.preview_srt_path = ass_name
            self.player.set_subtitle(ass_name)
            
            # [??뺣빍??筌ㅼ뮇??? ??깅뻻?類? ?怨밴묶??????뽰쁽???癒곕늄嚥??袁⑥쟿????덉쨮?⑥쥙臾?
            if force_reload and not self.player.is_playing():
                curr = self.player.get_time()
                if curr >= 0:
                    self.player.set_time(curr)
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f'[ERROR] apply_preview_subtitles ??쎈솭: {e}')
    def toggle_play(self):
        if self.player: is_p = self.player.toggle_play(); self.btn_play.config(text='일시정지' if is_p else '재생')
    def skip_time(self, ms): 
        if self.player: self.player.skip(ms)
    def on_seek_start(self, e):
        self.is_seeking = True
        self._was_playing_before_seek = self.player.is_playing() if self.player else False
        if self.player:
            self.player.set_mute(True)
            if not self._was_playing_before_seek:
                self.player.toggle_play() # 揶쏅벡??揶쏄퉮????袁る퉸 ??源???뽰삂
        self._update_seek_from_mouse(e)
    def on_seek_motion(self, e):
        if self.is_seeking: self._update_seek_from_mouse(e)
    def on_seek_release(self, e):
        if self.is_seeking: self._update_seek_from_mouse(e)
        self.is_seeking = False
        if self.player:
            if getattr(self, '_was_playing_before_seek', False):
                self.player.play() # ?癒?삋 ??源??怨밴묶????삠늺 ??源?
            else:
                self.player.pause() # ?癒?삋 ??깅뻻?類? ?怨밴묶????삠늺 ?類?
            # 筌앸맩??獒뺛끋????곸젫 ?????봺揶쎛 ??????됰선 ??꾩퍢????뺤쟿??
            self.root.after(100, lambda: self.player.set_mute(False) if self.player else None)
    def _update_seek_from_mouse(self, e):
        try:
            w = self.seek_bar.winfo_width()
            if w > 0 and self.player:
                pos = max(0.0, min(1.0, e.x / w))
                self.player.set_position(pos)
                self.seek_var.set(pos * 1000)
        except Exception as e: print(f'[WARN] ??쀪쾿獄???猷???살첒: {e}')


    def update_loop(self):
        if self.player:
            if not self.is_seeking:
                pos = self.player.get_position()
                if pos >= 0: self.seek_var.set(pos * 1000)
            curr_ms = self.player.get_time()
            total_ms = self.player.get_length()
            
            # [??뺣빍??筌ㅼ뮇??? VLC ?????????곴맒????볧???250ms) 域밸갭????袁る립 ???뵠????? 獄쎛?귐딇겧(High-Precision) ?袁⑥쟿??癰귣떯而?
            import time
            if not hasattr(self, '_last_vlc_ms'):
                self._last_vlc_ms = curr_ms
                self._vlc_clock = time.time()
                self._smooth_ms = curr_ms
            
            if curr_ms != self._last_vlc_ms:
                self._last_vlc_ms = curr_ms
                self._vlc_clock = time.time()
                self._smooth_ms = curr_ms
            elif self.player.is_playing() and not self.is_seeking:
                self._smooth_ms = curr_ms + (time.time() - self._vlc_clock) * 1000.0
            else:
                self._smooth_ms = curr_ms
            
            if self._smooth_ms >= 0 and total_ms > 0:
                c_m, c_s = divmod(int(self._smooth_ms/1000), 60); t_m, t_s = divmod(int(total_ms/1000), 60); self.lbl_time.config(text=f"{c_m:02d}:{c_s:02d} / {t_m:02d}:{t_s:02d}")
                self._refresh_overlay_time_state(curr_ms / 1000.0)
                self._update_overlay_timeline_playhead()
                
                # [??????遺욧퍕] ?袁⑹삺 ??源?餓λ쵐???癒?춵 筌≪뼐由?獄?揶쏅벡??(??곸젫 ?λ뜆?숃쳸? ??볧?????
                curr_sec = self._smooth_ms / 1000.0
                active_idx = -1
                for i, r in enumerate(self.results_data):
                    if r['s'] <= curr_sec <= r['e']:
                        active_idx = i
                        break
                
                if hasattr(self, '_last_active_idx') and self._last_active_idx != active_idx:
                    current_tab = self.notebook.index(self.notebook.select())
                    
                    # Treeview 揶쏅벡??
                    for item in self.tree.get_children():
                        val = self.tree.item(item)['values']
                        if val and int(val[0]) - 1 == active_idx:
                            self.tree.item(item, tags=('active',))
                            if current_tab == 1: self.tree.see(item) # ?癒?춵 ?귐딅뮞?????????춸 ??쎄쾿嚥?
                        else:
                            self.tree.item(item, tags=())
                    
                    # ??λ선 ?됰뗀以?揶쏅벡??(??쎄쾿嚥▲끉? ??? 筌롫뗄苑??뽯퓠?????類ㅼ뵥 ????묐뻬)
                    self.block_editor.set_active_row(active_idx, follow= (current_tab == 0))
                    self._last_active_idx = active_idx
                elif not hasattr(self, '_last_active_idx'):
                    self._last_active_idx = -2 # ?λ뜃由??

                if hasattr(self, 'block_editor'):
                    self.block_editor.set_active_time(curr_sec)

            if hasattr(self, 'btn_play'): self.btn_play.config(text='일시정지' if self.player.is_playing() else '재생')
        
        # ??쇰뻻揶쏄쑴苑??關湲???袁る퉸 16ms 雅뚯눊由경에?癰궰野?(?λ뜄??~60?袁⑥쟿??
        self.root.after(16, self.update_loop)
    def export_subtitles(self):
        if not self.results_data: return
        fmt = self.export_format.get()
        if fmt == "FCPXML":
            self.on_export_xml()
            return
            
        ext = "." + fmt.lower()
        initial = os.path.splitext(os.path.basename(self.current_video_path))[0]
        file_path = filedialog.asksaveasfilename(defaultextension=ext, initialfile=initial, filetypes=[(fmt, "*" + ext)])
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                if fmt == "SRT":
                    for i, r in enumerate(self.results_data):
                        s_r, e_r = r['s'], r['e']
                        if i < len(self.results_data) - 1 and e_r >= self.results_data[i+1]['s']: e_r = max(s_r + 0.1, self.results_data[i+1]['s'] - 0.05)
                        s = time.strftime('%H:%M:%S', time.gmtime(s_r)) + f",{int((s_r%1)*1000):03d}"; e = time.strftime('%H:%M:%S', time.gmtime(e_r)) + f",{int((e_r%1)*1000):03d}"; f.write(f"{i+1}\n{s} --> {e}\n{r['t']}\n\n")
                elif fmt == "TXT":
                    for r in self.results_data: f.write(f"[{round(r['s'], 2)}s] {r['t']}\n")
                elif fmt == "VTT":
                    f.write("WEBVTT\n\n")
                    for i, r in enumerate(self.results_data):
                        s_r, e_r = r['s'], r['e']
                        if i < len(self.results_data) - 1 and e_r >= self.results_data[i+1]['s']: e_r = max(s_r + 0.1, self.results_data[i+1]['s'] - 0.05)
                        s = time.strftime('%H:%M:%S', time.gmtime(s_r)) + f".{int((s_r%1)*1000):03d}"; e = time.strftime('%H:%M:%S', time.gmtime(e_r)) + f".{int((e_r%1)*1000):03d}"; f.write(f"{i+1}\n{s} --> {e}\n{r['t']}\n\n")
                elif fmt == "CSV":
                    import csv
                    writer = csv.writer(f)
                    writer.writerow(["Index", "Start", "End", "Text"])
                    for i, r in enumerate(self.results_data):
                        writer.writerow([i+1, r['s'], r['e'], r['t']])
            messagebox.showinfo('?꾨즺', '??λ릺?덉뒿?덈떎.')














