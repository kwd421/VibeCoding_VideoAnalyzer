import tkinter as tk
import customtkinter as ctk
from tkinter import ttk


def build_inspector_shell(self):
    inspector = tk.Frame(self.main_paned, bg=self.C['bg'])
    self.main_paned.add(inspector, minsize=280, width=340)

    insp_scroll = tk.Canvas(inspector, bg=self.C['bg'], highlightthickness=0, bd=0)
    insp_sb = ttk.Scrollbar(inspector, orient=tk.VERTICAL, command=insp_scroll.yview)
    insp_inner = tk.Frame(insp_scroll, bg=self.C['bg'])
    insp_inner.bind('<Configure>', lambda e: insp_scroll.configure(scrollregion=insp_scroll.bbox('all')))
    insp_scroll.create_window((0, 0), window=insp_inner, anchor='nw', tags='inner')
    insp_scroll.bind('<Configure>', lambda e: insp_scroll.itemconfig('inner', width=e.width))
    insp_scroll.configure(yscrollcommand=insp_sb.set)
    insp_sb.pack(side=tk.RIGHT, fill=tk.Y)
    insp_scroll.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    inspector.bind('<Enter>', lambda e: insp_scroll.bind_all('<MouseWheel>', lambda ev: insp_scroll.yview_scroll(int(-1 * (ev.delta / 120)), 'units')))
    inspector.bind('<Leave>', lambda e: insp_scroll.unbind_all('<MouseWheel>'))

    self.inspector_frame = inspector
    self.inspector_scroll_canvas = insp_scroll
    self.inspector_scrollbar = insp_sb
    self.inspector_inner = insp_inner
    return insp_inner


def make_inspector_button(self, parent, text, command, body_font=None, kind='secondary', height=38, width=None):
    palette = {
        'primary': dict(fg_color=self.C['accent'], hover_color='#0062CC', text_color='#FFFFFF'),
        'secondary': dict(fg_color=self.C['bg3'], hover_color=self.C['border'], text_color=self.C['text']),
        'danger': dict(fg_color='#FFF1F0', hover_color='#FFE5E2', text_color=self.C['red']),
        'purple': dict(fg_color=self.C['purple'], hover_color='#9342B5', text_color='#FFFFFF'),
        'orange': dict(fg_color=self.C['orange'], hover_color='#E08600', text_color='#FFFFFF'),
    }
    if body_font is None:
        body_font = ('Noto Sans KR', 11)
    kwargs = dict(text=text, command=command, height=height, corner_radius=14, border_width=0, font=body_font, **palette[kind])
    if width is not None:
        kwargs['width'] = width
    return ctk.CTkButton(parent, **kwargs)


def make_inspector_card(self, parent, title='', title_font=('Noto Sans KR', 12, 'bold')):
    shell = tk.Frame(parent, bg=self.C['bg'])
    shell.pack(fill=tk.X, padx=12, pady=(0, 6))
    card = ctk.CTkFrame(shell, fg_color=self.C['bg2'], corner_radius=18, border_width=1, border_color=self.C['border'])
    card.pack(fill=tk.X)
    if title:
        ctk.CTkLabel(card, text=title, text_color=self.C['text'], font=title_font).pack(anchor=tk.W, padx=16, pady=(14, 8))
    return card


def make_inspector_row(parent):
    row = ctk.CTkFrame(parent, fg_color='transparent', corner_radius=0)
    row.pack(fill=tk.X, padx=16, pady=4)
    return row


def make_inspector_sep(self, parent):
    ctk.CTkFrame(parent, fg_color=self.C['border'], height=1, corner_radius=999).pack(fill=tk.X, padx=16, pady=8)


def build_style_tab_shell(self):
    st_inner = ctk.CTkFrame(self.tab_style, fg_color='transparent', corner_radius=0)
    st_inner.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
    self.style_tab_inner = st_inner
    return st_inner


def make_style_row(self, parent, label, label_font):
    frame = ctk.CTkFrame(parent, fg_color='transparent', corner_radius=0)
    frame.pack(fill=tk.X, pady=8)
    ctk.CTkLabel(frame, text=label, text_color=self.C['text'], font=label_font, width=150, anchor='w').pack(side=tk.LEFT)
    return frame
