import tkinter as tk
from tkinter import ttk


def build_timeline_notebook(self, timeline_zone):
    self.notebook = ttk.Notebook(timeline_zone)
    self.notebook.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
    self.tab_canvas = tk.Frame(self.notebook, bg=self.C['bg'])
    self.notebook.add(self.tab_canvas, text=' \uB2E8\uC5B4 \uBE14\uB85D ')
    self.tab_overlay = tk.Frame(self.notebook, bg=self.C['bg'])
    self.notebook.add(self.tab_overlay, text=' \uC624\uBC84\uB808\uC774 \uD0C0\uC784\uB77C\uC778 ')
    self.tab_tree = tk.Frame(self.notebook, bg=self.C['bg2'])
    self.notebook.add(self.tab_tree, text=' \uC790\uB9C9 \uB9AC\uC2A4\uD2B8 ')
    self.tab_style = tk.Frame(self.notebook, bg=self.C['bg'])
    self.notebook.add(self.tab_style, text=' \uC790\uB9C9 \uC124\uC815 ')
    self.notebook.select(self.tab_canvas)


def build_tree_tab_static(self):
    self.tree = ttk.Treeview(self.tab_tree, columns=('no', 'start', 'end', 'text'), show='headings')
    self.tree.tag_configure('active', background='#D0E5FF')
    self.tree.heading('no', text='#')
    self.tree.heading('start', text='\uC2DC\uC791')
    self.tree.heading('end', text='\uC885\uB8CC')
    self.tree.heading('text', text='\uB300\uC0AC')
    self.tree.column('no', width=34, anchor=tk.CENTER)
    self.tree.column('start', width=70, anchor=tk.CENTER)
    self.tree.column('end', width=70, anchor=tk.CENTER)
    self.tree.column('text', width=400)
    scrollbar = ttk.Scrollbar(self.tab_tree, orient=tk.VERTICAL, command=self.tree.yview)
    self.tree.configure(yscrollcommand=scrollbar.set)
    self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)


def build_overlay_tab_static(self, body_font):
    overlay_toolbar = tk.Frame(self.tab_overlay, bg=self.C['bg'])
    overlay_toolbar.pack(fill=tk.X, padx=8, pady=(8, 4))
    self.btn_add_image_overlay = tk.Button(
        overlay_toolbar,
        text='\uC774\uBBF8\uC9C0 \uC624\uBC84\uB808\uC774 \uCD94\uAC00',
        command=self.add_image_overlay,
        bg=self.C['bg2'],
        fg=self.C['text'],
        relief='flat',
        bd=0,
        padx=10,
        pady=6,
        cursor='hand2',
    )
    self.btn_add_image_overlay.pack(side=tk.LEFT)
    self.btn_add_text_overlay = tk.Button(
        overlay_toolbar,
        text='\uD14D\uC2A4\uD2B8 \uC624\uBC84\uB808\uC774 \uCD94\uAC00',
        command=self.add_text_overlay,
        bg=self.C['bg2'],
        fg=self.C['text'],
        relief='flat',
        bd=0,
        padx=10,
        pady=6,
        cursor='hand2',
    )
    self.btn_add_text_overlay.pack(side=tk.LEFT, padx=(6, 0))
    self.btn_add_audio_clip = tk.Button(
        overlay_toolbar,
        text='\uC624\uB514\uC624 \uD074\uB9BD \uCD94\uAC00',
        command=self.add_audio_clip,
        bg=self.C['bg2'],
        fg=self.C['text'],
        relief='flat',
        bd=0,
        padx=10,
        pady=6,
        cursor='hand2',
    )
    self.btn_add_audio_clip.pack(side=tk.LEFT, padx=(6, 0))
    self.btn_add_video_clip = tk.Button(
        overlay_toolbar,
        text='\uBE44\uB514\uC624 \uD074\uB9BD \uCD94\uAC00',
        command=self.add_video_clip,
        bg=self.C['bg2'],
        fg=self.C['text'],
        relief='flat',
        bd=0,
        padx=10,
        pady=6,
        cursor='hand2',
    )
    self.btn_add_video_clip.pack(side=tk.LEFT, padx=(6, 0))
    self.use_subtitle_adapter_var = tk.BooleanVar(value=False)
    self.subtitle_adapter_check = tk.Checkbutton(
        overlay_toolbar,
        text='\uC790\uB9C9 \uC5B4\uB311\uD130',
        variable=self.use_subtitle_adapter_var,
        command=lambda: (self.refresh_overlay_preview(), self.refresh_overlay_timeline()),
        bg=self.C['bg'],
        fg=self.C['text'],
        selectcolor=self.C['bg3'],
        activebackground=self.C['bg'],
        activeforeground=self.C['text'],
        relief='flat',
        bd=0,
        highlightthickness=0,
        font=body_font,
    )
    self.subtitle_adapter_check.pack(side=tk.LEFT, padx=(8, 0))
    tk.Label(overlay_toolbar, text='\uBC30\uC728', bg=self.C['bg'], fg=self.C['text2'], font=body_font).pack(side=tk.LEFT, padx=(12, 4))
    self.overlay_zoom_var = tk.StringVar(value='1x')
    self.overlay_zoom_combo = ttk.Combobox(overlay_toolbar, textvariable=self.overlay_zoom_var, state='readonly', width=6, values=('1x', '2x', '4x', '8x'))
    self.overlay_zoom_combo.pack(side=tk.LEFT)
    tk.Label(overlay_toolbar, text='\uC2A4\uB0C5', bg=self.C['bg'], fg=self.C['text2'], font=body_font).pack(side=tk.LEFT, padx=(12, 4))
    self.overlay_snap_var = tk.StringVar(value='0.1\uCD08')
    self.overlay_snap_combo = ttk.Combobox(overlay_toolbar, textvariable=self.overlay_snap_var, state='readonly', width=12, values=('\uB044\uAE30', '0.1\uCD08', '\uD504\uB808\uC784'))
    self.overlay_snap_combo.pack(side=tk.LEFT)

    overlay_body = tk.Frame(self.tab_overlay, bg=self.C['bg'])
    overlay_body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
    overlay_timeline_wrap = tk.Frame(overlay_body, bg=self.C['bg'])
    overlay_timeline_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    self.overlay_timeline_canvas = tk.Canvas(overlay_timeline_wrap, bg=self.C['bg2'], highlightthickness=0)
    self.overlay_timeline_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    self.overlay_timeline_hscroll = ttk.Scrollbar(overlay_timeline_wrap, orient=tk.HORIZONTAL, command=self.overlay_timeline_canvas.xview)
    self.overlay_timeline_hscroll.pack(side=tk.BOTTOM, fill=tk.X)
    self.overlay_timeline_canvas.configure(xscrollcommand=self.overlay_timeline_hscroll.set)
    self._overlay_timeline_playhead = None
    self._overlay_timeline_cycle = {'key': None, 'index': 0, 'items': []}
    self._overlay_timeline_drag = {'item_id': None, 'mode': None, 'press_time': 0.0, 'origin_start': 0.0, 'origin_end': 0.0}

    self.overlay_props_canvas = None
    self.overlay_props_scroll = None
    self.overlay_props_inner = None
    self._overlay_props_window = None
    self.overlay_visible_check = None
    self.btn_overlay_forward = None
    self.btn_overlay_backward = None
    self.btn_overlay_front = None
    self.btn_overlay_back = None
    self.btn_apply_overlay_props = None
    self.btn_delete_overlay = None
    self.lbl_overlay_props = None
