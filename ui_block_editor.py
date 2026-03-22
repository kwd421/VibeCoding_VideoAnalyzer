import tkinter as tk
from tkinter import ttk

class UIBlockEditor:
    """[시니어 UI 분리] 단어 블록 마법진(Drag & Drop) 캔버스 관리"""
    
    @staticmethod
    def format_time(t_sec):
        m = int(t_sec // 60)
        s = t_sec % 60
        return f"{m:02d}:{s:05.2f}"

    @staticmethod
    def wheel_units(event):
        if event.delta == 0:
            return 0
        if hasattr(event, "num"):
            if event.num == 4:
                return -1
            if event.num == 5:
                return 1
        if tk.TkVersion and event.delta:
            return -1 if event.delta > 0 else 1 if event.delta < 0 else 0
        return int(-1 * (event.delta / 120))

    @staticmethod
    def is_vertical_scroll_event(event):
        return not bool(getattr(event, "state", 0) & 0x1)

    @property
    def player(self):
        """항상 최신 VLC player 인스턴스를 동적으로 반환"""
        return self._player_getter()

    def __init__(self, parent, root, transcript_manager, player_getter, on_tree_rebuild_request):
        self.parent = parent
        self.root = root
        self.transcript_manager = transcript_manager
        self._player_getter = player_getter  # [핵심] 항상 최신 player 참조를 반환하는 callable
        self.on_tree_rebuild_request = on_tree_rebuild_request
        
        # [Apple HIG 디자인] 블록 에디터 색상 팔레트
        self.BC = {
            'bg': '#F2F2F7', 'row': '#FFFFFF', 'row_alt': '#F9F9FB', # 메인 배경과 통일
            'word_fg': '#000000', 'word_border': '#e6b617', # Vrew 스타일 노란색
            'idx': '#86868B', 'time_s': '#5AC8FA', 'time_e': '#FF9500', 'sep': '#D1D1D6',
            'active': '#D0E5FF' # 재생 중 강조 색상
        }
        self.active_row_idx = -1
        
        self.block_canvas = tk.Canvas(parent, bg=self.BC['bg'], highlightthickness=0)
        self.block_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sc = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.block_canvas.yview)
        sc.pack(side=tk.RIGHT, fill=tk.Y)
        self.block_canvas.configure(yscrollcommand=sc.set)

        self.block_canvas.bind("<ButtonPress-1>", self.on_block_press)
        self.block_canvas.bind("<B1-Motion>", self.on_block_drag)
        self.block_canvas.bind("<ButtonRelease-1>", self.on_block_release)
        self.block_canvas.bind("<Double-1>", self.on_block_double)
        self.block_canvas.bind("<MouseWheel>", self.on_block_scroll)
        self.block_canvas.bind("<Shift-MouseWheel>", lambda e: "break")
        self.parent.bind("<MouseWheel>", self.on_block_scroll)
        self.parent.bind("<Shift-MouseWheel>", lambda e: "break")
        sc.bind("<MouseWheel>", self.on_block_scroll)
        sc.bind("<Shift-MouseWheel>", lambda e: "break")
        
        def _on_enter(e):
            self.root.bind_all("<Delete>", self.on_block_delete)
        def _on_leave(e):
            self.root.unbind_all("<Delete>")
            
        self.parent.bind("<Enter>", _on_enter)
        self.parent.bind("<Leave>", _on_leave)
        self.block_canvas.bind("<Button-3>", self.on_block_right_click)

        self.block_menu = tk.Menu(self.root, tearoff=0, bg='#2c2c2e', fg='#f5f5f7', activebackground='#0a84ff', activeforeground='white', font=('Segoe UI', 12))
        self.block_menu.add_command(label="분리: 현재 단어부터 다음 줄로 나누기", command=self.split_word_block)
        
        self.row_menu = tk.Menu(self.root, tearoff=0, bg='#2c2c2e', fg='#f5f5f7', activebackground='#0a84ff', activeforeground='white', font=('Segoe UI', 12))
        self.row_menu.add_command(label="병합: 위 대사와 합치기", command=lambda: self.merge_row_block(-1))
        self.row_menu.add_command(label="병합: 아래 대사와 합치기", command=lambda: self.merge_row_block(1))

        self.drag_data = {"items": [], "idx": -1, "w_idx": -1, "start_x": 0, "start_y": 0}
        self.row_y_map = []
        self.action_data = {}
        self.active_entry = None  # [사용자 요청] 현재 활성화된 편집창 추적
        self.active_entry_save_cb = None  # 강제 저장을 위한 콜백 저장

    def on_block_scroll(self, event):
        if not self.is_vertical_scroll_event(event):
            return "break"
        # [사용자 요청] Ctrl+휠: 단어 블록 또는 행/시간 미세 조정 및 즉시 재생
        if event.state & 0x4: # Ctrl key
            # [시니어 수정] 캔버스 좌표 점검 (스크롤 대응)
            cx, cy = self.block_canvas.canvasx(event.x), self.block_canvas.canvasy(event.y)
            item = self.block_canvas.find_closest(cx, cy)
            if not item: return "break"
            tags = self.block_canvas.gettags(item[0])
            
            # 1. 단어 블록 태그 (예: 1_2)
            word_tag = next((t for t in tags if "_" in t and not t.startswith("row_") and not t.startswith("time_") and t not in ["current", "word_block"]), None)
            # 2. 시작/종료 시간 텍스트 태그 (예: time_s_0)
            time_tag = next((t for t in tags if t.startswith("time_")), None)
            # 3. 행 전체 태그 감지
            row_tag = next((t for t in tags if t.startswith("row_")), None)
            
            if word_tag or time_tag or row_tag:
                try:
                    delta = -0.05 if event.delta > 0 else 0.05
                    results_data = self.transcript_manager.get_all()
                    
                    if word_tag:
                        # --- 개별 단어 조절 (알고리즘 리스트뷰와 통합) ---
                        idx, w_idx = map(int, word_tag.split("_"))
                        mid_x = (self.block_canvas.bbox(item)[0] + self.block_canvas.bbox(item)[2]) / 2
                        key = 's' if cx < mid_x else 'e'
                        target_word = results_data[idx]['words'][w_idx]
                        nv = max(0, target_word[key] + delta)
                        
                        valid = True
                        if key == 's':
                            # 이전 단어의 종료 시간(또는 이전 행의 종료 시간)보다 앞서지 않게
                            if nv >= target_word['e']: valid = False
                            if w_idx > 0 and nv < results_data[idx]['words'][w_idx-1]['e']: valid = False
                            if w_idx == 0 and idx > 0 and nv < results_data[idx-1]['e']: valid = False
                        else:
                            # 다음 단어의 시작 시간(또는 다음 행의 시작 시간)보다 늦지 않게
                            if nv <= target_word['s']: valid = False
                            if w_idx < len(results_data[idx]['words']) - 1 and nv > results_data[idx]['words'][w_idx+1]['s']: valid = False
                            if w_idx == len(results_data[idx]['words']) - 1 and idx < len(results_data) - 1 and nv > results_data[idx+1]['s']: valid = False
                        
                        if valid:
                            self.transcript_manager.save_state()
                            target_word[key] = round(nv, 3)
                            # 단어 조절이 완료되면 전체 행의 s, e도 갱신
                            results_data[idx]['s'] = min(w['s'] for w in results_data[idx]['words'])
                            results_data[idx]['e'] = max(w['e'] for w in results_data[idx]['words'])
                            self._sync_and_play(nv, fast=True, idx_to_update=idx)
                    
                    elif time_tag:
                        # --- 시작/종료 시간 조절 (리스트뷰와 100% 동일) ---
                        parts = time_tag.split("_")
                        key, idx = parts[1], int(parts[2])
                        nv = max(0, results_data[idx][key] + delta)
                        valid = True
                        if key == 's':
                            if nv >= results_data[idx]['e'] or (idx > 0 and nv < results_data[idx-1]['e']): valid = False
                        else: # key == 'e'
                            if nv <= results_data[idx]['s'] or (idx < len(results_data)-1 and nv > results_data[idx+1]['s']): valid = False
                        
                        if valid:
                            self.transcript_manager.save_state()
                            results_data[idx][key] = round(nv, 3)
                            # 리전 조절 시 내부 단어도 강제 싱크
                            if results_data[idx].get('words'):
                                if key == 's': results_data[idx]['words'][0]['s'] = nv
                                else: results_data[idx]['words'][-1]['e'] = nv
                            self._sync_and_play(nv, fast=True, idx_to_update=idx)
                    
                    elif row_tag:
                        # --- 행 배경 조절 ---
                        idx = int(row_tag.split("_")[1])
                        key = 's' if cx < 120 else 'e'
                        nv = max(0, results_data[idx][key] + delta)
                        valid = True
                        if key == 's':
                            if nv >= results_data[idx]['e'] or (idx > 0 and nv < results_data[idx-1]['e']): valid = False
                        else:
                            if nv <= results_data[idx]['s'] or (idx < len(results_data)-1 and nv > results_data[idx+1]['s']): valid = False
                        if valid:
                            self.transcript_manager.save_state()
                            results_data[idx][key] = round(nv, 3)
                            if results_data[idx].get('words'):
                                if key == 's': results_data[idx]['words'][0]['s'] = nv
                                else: results_data[idx]['words'][-1]['e'] = nv
                            self._sync_and_play(nv, fast=True, idx_to_update=idx)
                except: pass
            return "break"
        
        units = self.wheel_units(event)
        if units != 0:
            self.block_canvas.yview_scroll(units, "units")
            return "break"

    def _edit_word_inline(self, idx, w_idx):
        """[사용자 요청] 단어를 클릭했을 때 그 위치에 입력창을 띄워 편집"""
        # [사용자 요청] 이미 편집 중인 창이 있다면 저장 후 닫기
        if self.active_entry_save_cb:
            self.active_entry_save_cb()

        results_data = self.transcript_manager.get_all()
        if idx >= len(results_data) or w_idx >= len(results_data[idx].get('words', [])): return
        
        w_obj = results_data[idx]['words'][w_idx]
        current_text = w_obj['word']
        
        # 캔버스 상의 해당 단어 텍스트 아이템 찾기
        tag = f"{idx}_{w_idx}"
        bbox = self.block_canvas.bbox(tag)
        if not bbox: return
        
        x1, y1, x2, y2 = bbox
        
        # Entry 위젯 생성 (폰트 크기 13pt로 상향)
        entry = tk.Entry(self.block_canvas, font=("Noto Sans KR", 13), justify=tk.CENTER, bd=0, highlightthickness=1, highlightbackground='#007AFF')
        entry.insert(0, current_text)
        
        # [사용자 요청] 스크롤 시 위치가 어긋나지 않도록 canvas.create_window 사용
        self.block_canvas.create_window(x1-2, y1-2, window=entry, width=(x2-x1)+4, height=(y2-y1)+4, anchor='nw', tag="editing_entry")
        entry.focus_set()
        entry.selection_range(0, tk.END)

        import tkinter.font as tkfont
        _fnt = tkfont.Font(font=("Noto Sans KR", 13))
        
        def _resize_entry(event=None):
            if not entry.winfo_exists(): return
            txt = entry.get()
            tw = _fnt.measure(txt) + 20 # 여백 포함
            new_w = max((x2-x1)+4, tw)
            
            # [시니어 모션 렌더링] 커지는 폭만큼 우측 블록들을 실시간으로 밀어냄
            if hasattr(entry, '_prev_w'):
                delta = new_w - entry._prev_w
                if delta != 0:
                    for i in range(w_idx + 1, len(results_data[idx]['words'])):
                        self.block_canvas.move(f"{idx}_{i}", delta, 0)
            
            entry._prev_w = new_w
            self.block_canvas.itemconfigure("editing_entry", width=new_w)
            
        entry._prev_w = (x2-x1)+4
        entry.bind("<KeyRelease>", _resize_entry)

        def _save(*_):
            if not entry.winfo_exists(): return
            new_val = entry.get().strip()
            # 중복 실행 방지를 위해 콜백 먼저 제거
            self.active_entry_save_cb = None
            
            if new_val and new_val != current_text:
                self.transcript_manager.save_state()
                w_obj['word'] = new_val
                # 문장 전체 텍스트 갱신
                results_data[idx]['t'] = ' '.join(w['word'].strip() for w in results_data[idx]['words'])
                self.rebuild_tree_and_render()
            else:
                self.render_block_view()
            
            if entry.winfo_exists():
                entry.destroy()
            self.active_entry = None

        self.active_entry = entry
        self.active_entry_save_cb = _save
            
        entry.bind("<Return>", _save)
        entry.bind("<FocusOut>", _save)
        entry.bind("<Escape>", lambda e: [entry.destroy(), self.render_block_view()])

    def _sync_and_play(self, time_val, fast=False, idx_to_update=None):
        if fast and idx_to_update is not None:
            # [시니어 최적화] 전체 리빌드를 건너뛰고 캔버스 라벨만 즉시 수정 (렉 방지)
            self._update_canvas_times_live(idx_to_update)
            self.rebuild_tree_and_render(fast=True)
        else:
            self.rebuild_tree_and_render(fast=False)
            
        if self.player:
            self.player.set_time(int(time_val * 1000))
            self.player.play()

    def _update_canvas_times_live(self, idx):
        """캔버스 전체를 다시 그리지 않고 특정 행의 시간 텍스트만 실시간으로 교체"""
        results_data = self.transcript_manager.get_all()
        if idx < 0 or idx >= len(results_data): return
        r = results_data[idx]
        
        # 시작 시간 라벨 업데이트
        s_tag = f"time_s_{idx}"
        items_s = self.block_canvas.find_withtag(s_tag)
        if items_s: self.block_canvas.itemconfig(items_s[0], text=self.format_time(r['s']))
        
        # 종료 시간 라벨 업데이트
        e_tag = f"time_e_{idx}"
        items_e = self.block_canvas.find_withtag(e_tag)
        if items_e: self.block_canvas.itemconfig(items_e[0], text=self.format_time(r['e']))

    def set_active_row(self, idx, follow=False):
        """현재 재생 중인 행의 번호를 설정하고 배경색을 즉시 갱신"""
        if self.active_row_idx == idx: return
        
        old_idx = self.active_row_idx
        self.active_row_idx = idx
        
        # 전체를 다시 그리지 않고 태그를 이용해 배경색만 실시간 교체 (성능 최적화)
        BC = self.BC
        # 이전 강조 행 복구
        if old_idx != -1:
            old_color = BC['row'] if old_idx % 2 == 0 else BC['row_alt']
            self.block_canvas.itemconfig(f"row_{old_idx}", fill=old_color)
            
        # 새로운 강조 행 적용
        if idx != -1:
            self.block_canvas.itemconfig(f"row_{idx}", fill=BC['active'])
            # 대사 줄이 화면 영역을 벗어나면 자동 스크롤 추적 (요청 시에만)
            if follow: self._see_row(idx)

    def set_active_time(self, curr_sec):
        """현재 재생 시간에 해당하는 단어 블록을 찾아 파란색으로 강조"""
        if not hasattr(self, 'active_word_id'): self.active_word_id = None
        if not hasattr(self, 'active_word_bg'): self.active_word_bg = None
        
        target_idx, target_w_idx = None, None
        if self.active_row_idx != -1:
            idx = self.active_row_idx
            results_data = self.transcript_manager.get_all()
            if 0 <= idx < len(results_data):
                words = results_data[idx].get('words', [])
                for i, w in enumerate(words):
                    ws = w['s'] if isinstance(w, dict) else w.s
                    we = w['e'] if isinstance(w, dict) else w.e
                    
                    # [시니어] 정확히 이 단어 구간 안에 있으면 즉시 선택하고 종료 (0.05초 여유)
                    if ws <= curr_sec <= we + 0.05:
                        target_idx, target_w_idx = idx, i
                        break
                    
                    # [시니어] 아직 시작 안 한 단어에 도달했다면 (0.05초 여유)
                    if ws > curr_sec + 0.05:
                        # 단어 사이 무음(Gap) 구간이면 직전 단어를 유지하여 깜빡임 방지
                        if i > 0:
                            target_idx, target_w_idx = idx, i - 1
                        break
        
        new_active_id = f"{target_idx}_{target_w_idx}" if target_idx is not None else None
        
        # 현재 활성 블록 변경 시 색상 전환
        if getattr(self, 'active_word_id', None) != new_active_id:
            # 이전 활성 블록 색상 원상 복구
            if self.active_word_id:
                old_rect = self.block_canvas.find_withtag(f"word_block&&{self.active_word_id}")
                if old_rect and self.active_word_bg:
                    self.block_canvas.itemconfig(old_rect[0], fill=self.active_word_bg)
            
            # 새 블록 강조
            self.active_word_id = new_active_id
            if new_active_id:
                rects = self.block_canvas.find_withtag(f"word_block&&{new_active_id}")
                if rects:
                    try:
                        self.active_word_bg = self.block_canvas.itemcget(rects[0], 'fill')
                        self.block_canvas.itemconfig(rects[0], fill='#80CFFF') # Lighter Blue (User Request)
                    except: pass

    def _see_row(self, idx):
        """[사용자 요청] 현재 화면에 보이는 마지막 대사가 끝난 후에만 스크롤 (페이지 단위)"""
        try:
            r_map = next((r for r in self.row_y_map if r['idx'] == idx), None)
            if not r_map: return
            
            # 캔버스에서 현재 보이는 영역 계산
            canvas_h = self.block_canvas.winfo_height()
            if canvas_h <= 0: return
            scroll_top = self.block_canvas.canvasy(0)
            scroll_bottom = scroll_top + canvas_h
            
            # 활성 행이 현재 보이는 영역 밖이면 스크롤
            if r_map['y_end'] > scroll_bottom or r_map['y_start'] < scroll_top:
                all_bbox = self.block_canvas.bbox("all")
                if all_bbox:
                    total_h = all_bbox[3] - all_bbox[1]
                    if total_h > 0:
                        self.block_canvas.yview_moveto(r_map['y_start'] / total_h)
        except: pass

    def rebuild_tree_and_render(self, fast=False):
        # 트리뷰 갱신 요청을 부모에게 전달
        self.on_tree_rebuild_request(fast=fast)
        if not fast:
            self.render_block_view()

    def on_block_right_click(self, event):
        x, y = self.block_canvas.canvasx(event.x), self.block_canvas.canvasy(event.y)
        item = self.block_canvas.find_withtag("current")
        if not item: return
        tags = self.block_canvas.gettags(item[0])
        
        word_tag = next((t for t in tags if "_" in t and not t.startswith("row_") and not t.startswith("time_") and t not in ["current", "word_block"]), None)
        if word_tag:
            try:
                idx, w_idx = map(int, word_tag.split("_"))
                self.action_data = {"idx": idx, "w_idx": w_idx}
                self.block_menu.post(event.x_root, event.y_root)
            except: pass
        else:
            time_tag = next((t for t in tags if str(t).startswith("time_")), None)
            row_tag = next((t for t in tags if str(t).startswith("row_")), None)
            if time_tag:
                try:
                    idx = int(time_tag.split("_")[2])
                    self.action_data = {"idx": idx}
                    self.row_menu.post(event.x_root, event.y_root)
                except: pass
            elif row_tag:
                try:
                    idx = int(row_tag.split("_")[1])
                    self.action_data = {"idx": idx}
                    self.row_menu.post(event.x_root, event.y_root)
                except: pass

    def on_block_delete(self, event):
        if isinstance(self.root.focus_get(), (tk.Entry, tk.Text)): return
        item = self.block_canvas.find_withtag("current")
        if not item: return
        tags = self.block_canvas.gettags(item[0])
        
        word_tag = next((t for t in tags if "_" in t and not t.startswith("row_") and not t.startswith("time_") and t not in ["current", "word_block"]), None)
        if word_tag:
            try:
                idx, w_idx = map(int, word_tag.split("_"))
                self.action_data = {"idx": idx, "w_idx": w_idx}
                self.delete_word_block()
            except: pass
        else:
            time_tag = next((t for t in tags if str(t).startswith("time_")), None)
            row_tag = next((t for t in tags if str(t).startswith("row_")), None)
            if time_tag:
                try:
                    idx = int(time_tag.split("_")[2])
                    self.action_data = {"idx": idx}
                    self.delete_row_block()
                except: pass
            elif row_tag:
                try:
                    idx = int(row_tag.split("_")[1])
                    self.action_data = {"idx": idx}
                    self.delete_row_block()
                except: pass

    def split_word_block(self):
        idx, w_idx = self.action_data.get("idx"), self.action_data.get("w_idx")
        if idx is None or w_idx is None: return
        results_data = self.transcript_manager.get_all()
        words = results_data[idx].get('words', [])
        if not words or w_idx == 0 or w_idx >= len(words): return
        
        self.transcript_manager.save_state()
        new_words = words[w_idx:]
        results_data[idx]['words'] = words[:w_idx]
        
        def _update_row(i):
            w_ls = results_data[i]['words']
            w_ls.sort(key=lambda x: x['s'])
            results_data[i]['t'] = ' '.join(w['word'].strip() for w in w_ls)
            results_data[i]['s'] = w_ls[0]['s']
            results_data[i]['e'] = w_ls[-1]['e']
            
        _update_row(idx)
        new_row = {'words': new_words, 't': '', 's': 0, 'e': 0}
        results_data.insert(idx + 1, new_row)
        _update_row(idx + 1)
        
        self.rebuild_tree_and_render()

    def delete_word_block(self):
        """[사용자 요청] 단어 블록 우클릭 -> 삭제"""
        idx, w_idx = self.action_data.get("idx"), self.action_data.get("w_idx")
        if idx is None or w_idx is None: return
        results_data = self.transcript_manager.get_all()
        words = results_data[idx].get('words', [])
        if not words or w_idx < 0 or w_idx >= len(words): return
        
        self.transcript_manager.save_state()
        words.pop(w_idx)
        
        if not words:
            results_data.pop(idx)
        else:
            w_ls = results_data[idx]['words']
            w_ls.sort(key=lambda x: x['s'])
            results_data[idx]['t'] = ' '.join(w['word'].strip() for w in w_ls)
            results_data[idx]['s'] = w_ls[0]['s']
            results_data[idx]['e'] = w_ls[-1]['e']
            
        self.rebuild_tree_and_render()

    def delete_row_block(self):
        """[사용자 요청] 대사 줄 전체 우클릭 -> 삭제"""
        idx = self.action_data.get("idx")
        if idx is None: return
        results_data = self.transcript_manager.get_all()
        if idx < 0 or idx >= len(results_data): return
        
        self.transcript_manager.save_state()
        results_data.pop(idx)
        self.rebuild_tree_and_render()

    def merge_row_block(self, direction):
        idx = self.action_data.get("idx")
        if idx is None: return
        results_data = self.transcript_manager.get_all()
        target_idx = idx + direction
        if target_idx < 0 or target_idx >= len(results_data): return
        
        base_idx = min(idx, target_idx)
        merge_idx = max(idx, target_idx)
        
        self.transcript_manager.save_state()
        
        w1 = results_data[base_idx].get('words', [])
        w2 = results_data[merge_idx].get('words', [])
        
        if not w1 and results_data[base_idx].get('t'):
            w1 = [{'word': results_data[base_idx]['t'], 's': results_data[base_idx]['s'], 'e': results_data[base_idx]['e']}]
        if not w2 and results_data[merge_idx].get('t'):
            w2 = [{'word': results_data[merge_idx]['t'], 's': results_data[merge_idx]['s'], 'e': results_data[merge_idx]['e']}]
            
        results_data[base_idx]['words'] = w1 + w2
        w_ls = results_data[base_idx]['words']
        if w_ls:
            w_ls.sort(key=lambda x: x['s'])
            results_data[base_idx]['t'] = ' '.join(w['word'].strip() for w in w_ls)
            results_data[base_idx]['s'] = w_ls[0]['s']
            results_data[base_idx]['e'] = w_ls[-1]['e']
            
        results_data.pop(merge_idx)
        self.rebuild_tree_and_render()

    def create_rounded_rect(self, canvas, x1, y1, x2, y2, radius=8, **kwargs):
        """Tkinter 캔버스에 둥근 사각형(Rounded Rectangle)을 그리는 헬퍼 함수"""
        points = [x1+radius, y1,
                  x1+radius, y1,
                  x2-radius, y1,
                  x2-radius, y1,
                  x2, y1,
                  x2, y1+radius,
                  x2, y1+radius,
                  x2, y2-radius,
                  x2, y2-radius,
                  x2, y2,
                  x2-radius, y2,
                  x2-radius, y2,
                  x1+radius, y2,
                  x1+radius, y2,
                  x1, y2,
                  x1, y2-radius,
                  x1, y2-radius,
                  x1, y1+radius,
                  x1, y1+radius,
                  x1, y1]
        return canvas.create_polygon(points, **kwargs, smooth=True)

    def render_block_view(self):
        if not hasattr(self, 'block_canvas') or not self.block_canvas.winfo_exists(): return
        self.block_canvas.delete("all")
        self.row_y_map = []
        self.active_word_id = None
        self.active_word_bg = None
        results_data = self.transcript_manager.get_all()
        BC = self.BC
        
        # [사용자 요청 6] 자막 리스트처럼 컬럼 헤더 추가
        hdr_y = 4
        self.block_canvas.create_rectangle(8, hdr_y, 3000, hdr_y + 28, fill='#E8E8ED', outline='')
        self.block_canvas.create_text(26, hdr_y + 14, text='#', fill='#86868B', anchor=tk.CENTER, font=('Noto Sans KR', 9, 'bold'))
        self.block_canvas.create_text(92, hdr_y + 14, text='시작시간', fill='#86868B', anchor=tk.CENTER, font=('Noto Sans KR', 9, 'bold'))
        self.block_canvas.create_text(187, hdr_y + 14, text='종료시간', fill='#86868B', anchor=tk.CENTER, font=('Noto Sans KR', 9, 'bold'))
        self.block_canvas.create_text(250, hdr_y + 14, text='대사', fill='#86868B', anchor=tk.W, font=('Noto Sans KR', 9, 'bold'))
        self.block_canvas.create_line(45, hdr_y + 4, 45, hdr_y + 24, fill='#D1D1D6', width=1)
        self.block_canvas.create_line(140, hdr_y + 4, 140, hdr_y + 24, fill='#D1D1D6', width=1)
        self.block_canvas.create_line(235, hdr_y + 4, 235, hdr_y + 24, fill='#D1D1D6', width=1)
        self.block_canvas.create_line(8, hdr_y + 28, 3000, hdr_y + 28, fill='#C7C7CC', width=1)
        y_offset = hdr_y + 32
        
        for idx, r in enumerate(results_data):
            # [사용자 요청] 재생 중인 행은 강조 색상 적용, 아니면 교차 색상
            if idx == self.active_row_idx:
                row_color = BC['active']
            else:
                row_color = BC['row'] if idx % 2 == 0 else BC['row_alt']
            
            row_id = self.block_canvas.create_rectangle(8, y_offset, 3000, y_offset + 38, fill=row_color, outline="", tags=(f"row_{idx}", "row_bg"))
            self.block_canvas.tag_lower(row_id)
            self.block_canvas.create_line(8, y_offset + 38, 3000, y_offset + 38, fill='#E5E5E7', width=1)
            
            # 행 번호
            self.block_canvas.create_text(26, y_offset + 19, text=f"{idx+1}", fill='#000000', anchor=tk.CENTER, font=("Noto Sans KR", 12))
            
            def _jump(e, t):
                if self.player:
                    self.player.set_time(int(t * 1000))
                    self.player.play()

            # [사용자 요청 1,2] 시작 시간 — 클릭 시 점프 + time_s 태그로 Ctrl+휠 감지
            start_txt = self.block_canvas.create_text(92, y_offset + 19, text=self.format_time(r.get('s',0)), fill='#000000', anchor=tk.CENTER, font=("Noto Sans KR", 13), tags=(f"time_s_{idx}",))
            self.block_canvas.tag_bind(start_txt, "<Button-1>", lambda e, s=r.get('s',0): _jump(e, s))
            
            # [사용자 요청 1,2] 종료 시간 — 클릭 시 점프 + time_e 태그로 Ctrl+휠 감지
            end_txt = self.block_canvas.create_text(187, y_offset + 19, text=self.format_time(r.get('e',0)), fill='#000000', anchor=tk.CENTER, font=("Noto Sans KR", 13), tags=(f"time_e_{idx}",))
            self.block_canvas.tag_bind(end_txt, "<Button-1>", lambda e, s=r.get('e',0): _jump(e, s))

            # 컬럼 구분선
            self.block_canvas.create_line(45, y_offset + 6, 45, y_offset + 32, fill='#D1D1D6', width=1)
            self.block_canvas.create_line(140, y_offset + 10, 140, y_offset + 28, fill='#D1D1D6', width=1)
            self.block_canvas.create_line(235, y_offset + 6, 235, y_offset + 32, fill='#D1D1D6', width=1)
            
            x_offset = 250
            words = r.get('words', [])
            
            refined_words = []
            for w_obj in words:
                sub_txt = w_obj.get('word', '').strip()
                sub_parts = sub_txt.split()
                if len(sub_parts) > 1:
                    sub_dur = (w_obj['e'] - w_obj['s']) / max(1, len(sub_parts))
                    for i, p in enumerate(sub_parts):
                        refined_words.append({'word': p, 's': w_obj['s'] + i*sub_dur, 'e': w_obj['s'] + (i+1)*sub_dur})
                elif sub_txt:
                    refined_words.append({'word': sub_txt, 's': w_obj['s'], 'e': w_obj['e']})
            words = refined_words
            
            if not words and r.get('t'):
                s_t, e_t = r['s'], r['e']
                split_t = r['t'].split()
                if split_t:
                    dur = (e_t - s_t) / max(1, len(split_t))
                    words = [{'word': wt, 's': s_t + i*dur, 'e': s_t + (i+1)*dur} for i, wt in enumerate(split_t)]
            
            # [시니어 최적화] 렌더링 시 데이터 구조가 바뀌면 Ctrl+Z에 영향을 줄 수 있으므로, 
            # 단어 블록이 이미 충분히 세분화되어 있다면 덮어쓰지 않음
            if not r.get('words') or len(r.get('words')) < len(words):
                results_data[idx]['words'] = words

            # [사용자 요청] 배경색 불투명도 70% 시뮬레이션 (Color Blending)
            # 행 배경색에 따라 노란색(#ffca1a)을 70% 혼합하여 투명 느낌 구현
            if idx == self.active_row_idx:
                row_word_bg = '#F1D25F' # On Active Blue
            elif idx % 2 == 0:
                row_word_bg = '#FFDA5F' # On White
            else:
                row_word_bg = '#FDD85E' # On Light Gray

            for w_idx, w_obj in enumerate(words):
                text = w_obj['word']
                # [사용자 요청 5] 여백 축소: 오프셋 8px
                text_id = self.block_canvas.create_text(x_offset + 8, y_offset + 19, text=text, fill=BC['word_fg'], anchor=tk.W, font=("Noto Sans KR", 13))
                bbox = self.block_canvas.bbox(text_id)
                if bbox:
                    # [사용자 요청 5] 양옆 여백 16px로 축소
                    w_width = bbox[2] - bbox[0] + 16
                    rect_id = self.create_rounded_rect(self.block_canvas, x_offset, y_offset + 4, x_offset + w_width, y_offset + 34, radius=10, fill=row_word_bg, outline='#FFFFFF', width=1.5, tags=("word_block", f"{idx}_{w_idx}"))
                    self.block_canvas.tag_lower(rect_id, text_id)
                    self.block_canvas.addtag_withtag(f"{idx}_{w_idx}", text_id)
                    # [사용자 요청 5] 블록 간 간격 5px로 축소
                    x_offset += w_width + 5
                    
                    def _enter(e, r_id=rect_id, cid=f"{idx}_{w_idx}"):
                        if getattr(self, 'active_word_id', None) != cid:
                            self.block_canvas.itemconfig(r_id, fill='#FFD700')
                    def _leave(e, r_id=rect_id, c=row_word_bg, cid=f"{idx}_{w_idx}"):
                        if getattr(self, 'active_word_id', None) != cid:
                            self.block_canvas.itemconfig(r_id, fill=c)
                    self.block_canvas.tag_bind(rect_id, "<Enter>", _enter)
                    self.block_canvas.tag_bind(rect_id, "<Leave>", _leave)
                    self.block_canvas.tag_bind(text_id, "<Enter>", _enter)
                    self.block_canvas.tag_bind(text_id, "<Leave>", _leave)
            
            self.row_y_map.append({'idx': idx, 'y_start': y_offset, 'y_end': y_offset + 38})
            y_offset += 42
            
        self.block_canvas.configure(scrollregion=(0, 0, 3000, y_offset + 20))

    def on_block_press(self, event):
        # [사용자 요청] 편집 중 다른 곳 클릭 시 자동 저장
        if self.active_entry_save_cb:
            self.active_entry_save_cb()

        x, y = self.block_canvas.canvasx(event.x), self.block_canvas.canvasy(event.y)
        item = self.block_canvas.find_withtag("current")
        if not item: return
        tags = self.block_canvas.gettags(item[0])
        word_tag = next((t for t in tags if "_" in t and t not in ["current", "word_block"] and not t.startswith("row_")), None)
        if not word_tag: return
        
        try:
            idx_str, w_idx_str = word_tag.split("_")
            self.drag_data["idx"] = int(idx_str)
            self.drag_data["w_idx"] = int(w_idx_str)
            self.drag_data["start_x"] = x
            self.drag_data["start_y"] = y
            self.drag_data["press_raw_x"] = event.x
            self.drag_data["press_raw_y"] = event.y
            
            items = self.block_canvas.find_withtag(word_tag)
            self.drag_data["items"] = items
            for it in items:
                self.block_canvas.tag_raise(it)
        except: pass

    def on_block_drag(self, event):
        if not getattr(self, 'drag_data', {}).get("items"): return
        
        # [사용자 요청 3] 이동 제한: 중간 단어는 드래그 원천 봉쇄
        s_idx = self.drag_data["idx"]
        w_idx = self.drag_data["w_idx"]
        results_data = self.transcript_manager.get_all()
        n_words = len(results_data[s_idx].get('words', []))
        is_first = (w_idx == 0)
        is_last = (w_idx == n_words - 1)
        if not is_first and not is_last:
            return  # 중간 단어는 드래그 불가

        x, y = self.block_canvas.canvasx(event.x), self.block_canvas.canvasy(event.y)
        dx = x - self.drag_data["start_x"]
        dy = y - self.drag_data["start_y"]
        for it in self.drag_data["items"]:
            self.block_canvas.move(it, dx, dy)
        self.drag_data["start_x"] = x
        self.drag_data["start_y"] = y
        
        self.block_canvas.delete("drop_highlight")
        
        target = None
        for rmap in self.row_y_map:
            # 병합 영역: 각 라인의 중심부 14px만 허용 (상하 12px씩 축소하여 삽입 영역 확보)
            if rmap['y_start'] + 12 <= y <= rmap['y_end'] - 12:
                target = {'type': 'merge', 'idx': rmap['idx']}
                break
                
        if target is None:
            # 병합이 아니면 무조건 삽입 (대사 사이 공간 전체가 인서트 히트박스로 동작)
            best_idx = 0
            for rmap in self.row_y_map:
                mid_y = (rmap['y_start'] + rmap['y_end']) / 2.0
                if y > mid_y:
                    best_idx = rmap['idx'] + 1
            target = {'type': 'insert', 'idx': best_idx}
        
        if target is not None:
            results_data = self.transcript_manager.get_all()
            n_words = len(results_data[s_idx].get('words', []))
            is_first = (w_idx == 0)
            is_last = (w_idx == n_words - 1)
            
            # [사용자 요청 3] 방향 제한: 첫 단어→위로만, 마지막 단어→아래로만
            is_valid = True
            if target['type'] == 'merge':
                t_idx = target['idx']
                if t_idx == s_idx:
                    is_valid = False
                elif is_first and t_idx == s_idx - 1:
                    pass  # 첫 단어 → 바로 위 대사로 OK
                elif is_last and t_idx == s_idx + 1:
                    pass  # 마지막 단어 → 바로 아래 대사로 OK
                else:
                    is_valid = False
            elif target['type'] == 'insert':
                if n_words <= 1:
                    is_valid = False
                else:
                    t_idx = target['idx']
                    if is_first and t_idx == s_idx:
                        pass # 첫 단어 -> 바로 위로 삽입 OK
                    elif is_last and t_idx == s_idx + 1:
                        pass # 마지막 단어 -> 바로 아래로 삽입 OK
                    else:
                        is_valid = False

            if is_valid:
                if target['type'] == 'merge':
                    rmap = next(r for r in self.row_y_map if r['idx'] == target['idx'])
                    # [사용자 요청] 더 진하고 두꺼운 시각화 (#0A84FF, width=4)
                    self.block_canvas.create_rectangle(8, rmap['y_start'], 3000, rmap['y_end'], fill="", outline='#0A84FF', width=4, dash=(3,2), tags="drop_highlight")
                elif target['type'] == 'insert':
                    insert_idx = target['idx']
                    if insert_idx < len(self.row_y_map):
                        rmap = self.row_y_map[insert_idx]
                        y_pos = rmap['y_start'] - 2
                    else:
                        rmap = self.row_y_map[-1]
                        y_pos = rmap['y_end'] + 2
                    # [사용자 요청] 더 진하고 두꺼운 시각화 (#0A84FF, width=4)
                    self.block_canvas.create_line(8, y_pos, 3000, y_pos, fill='#0A84FF', width=4, dash=(3,2), tags="drop_highlight")
                
                self.block_canvas.tag_raise("drop_highlight")
                for it in self.drag_data["items"]:
                    self.block_canvas.tag_raise(it)

    def on_block_release(self, event):
        if not getattr(self, 'drag_data', {}).get("items"): return
        y = self.block_canvas.canvasy(event.y)
        s_idx = self.drag_data["idx"]
        w_idx = self.drag_data["w_idx"]
        
        # 클릭과 드래그 구분 (이동 5px 미만 → 편집 모드)
        dist = ((event.x - self.drag_data.get("press_raw_x", 0))**2 + (event.y - self.drag_data.get("press_raw_y", 0))**2)**0.5
        if dist < 5:
            self.block_canvas.delete("drop_highlight")
            self._edit_word_inline(s_idx, w_idx)
            self.drag_data = {"items": []}
            return

        # 드롭 대상 탐색
        target = None
        for rmap in self.row_y_map:
            if rmap['y_start'] + 12 <= y <= rmap['y_end'] - 12:
                target = {'type': 'merge', 'idx': rmap['idx']}
                break
                
        if target is None:
            best_idx = 0
            for rmap in self.row_y_map:
                mid_y = (rmap['y_start'] + rmap['y_end']) / 2.0
                if y > mid_y:
                    best_idx = rmap['idx'] + 1
            target = {'type': 'insert', 'idx': best_idx}
                
        if target is not None:
            results_data = self.transcript_manager.get_all()
            n_words = len(results_data[s_idx].get('words', []))
            is_first = (w_idx == 0)
            is_last = (w_idx == n_words - 1)
            
            # [사용자 요청 3] 방향 제한: 첫 단어→위로만, 마지막 단어→아래로만
            is_valid = True
            if target['type'] == 'merge':
                t_idx = target['idx']
                if t_idx == s_idx:
                    is_valid = False
                elif is_first and t_idx == s_idx - 1:
                    pass  # OK
                elif is_last and t_idx == s_idx + 1:
                    pass  # OK
                else:
                    is_valid = False
            elif target['type'] == 'insert':
                if n_words <= 1:
                    is_valid = False
                else:
                    t_idx = target['idx']
                    if is_first and t_idx == s_idx:
                        pass # OK
                    elif is_last and t_idx == s_idx + 1:
                        pass # OK
                    else:
                        is_valid = False
                
            if not is_valid:
                self.block_canvas.delete("drop_highlight")
                self.drag_data = {"items": []}
                self.render_block_view()
                return
            else:
                self.transcript_manager.save_state()
                w_obj = results_data[s_idx]['words'].pop(w_idx)
                affected_indices = set([s_idx])
                
                if target['type'] == 'merge':
                    target_idx = target['idx']
                    if 'words' not in results_data[target_idx]:
                         results_data[target_idx]['words'] = []
                    results_data[target_idx]['words'].append(w_obj)
                    affected_indices.add(target_idx)
                elif target['type'] == 'insert':
                    insert_idx = target['idx']
                    new_row = {'t': '', 's': w_obj['s'], 'e': w_obj['e'], 'words': [w_obj]}
                    results_data.insert(insert_idx, new_row)
                    adjusted_s_idx = s_idx + 1 if insert_idx <= s_idx else s_idx
                    affected_indices.add(adjusted_s_idx)
                    affected_indices.add(insert_idx)
                
                for u in affected_indices:
                    w_ls = results_data[u]['words']
                    if w_ls:
                        w_ls.sort(key=lambda x: x['s'])
                        new_t = ' '.join(w['word'].strip() for w in w_ls)
                        results_data[u]['t'] = new_t
                        results_data[u]['s'] = w_ls[0]['s']
                        results_data[u]['e'] = w_ls[-1]['e']
                    else:
                        results_data[u]['t'] = ""
    
                empty_indices = [idx for idx in sorted(list(affected_indices), reverse=True) if not results_data[idx].get('words', [])]
                for idx in empty_indices:
                    results_data.pop(idx)
    
                self.rebuild_tree_and_render()
        
        self.block_canvas.delete("drop_highlight")
        self.drag_data = {"items": []}
        self.render_block_view()
        
    def on_block_double(self, event):
        y = self.block_canvas.canvasy(event.y)
        for rmap in self.row_y_map:
            if rmap['y_start'] <= y <= rmap['y_end']:
                results_data = self.transcript_manager.get_all()
                r = results_data[rmap['idx']]
                if self.player:
                    self.player.set_time(int(r.get('s', 0) * 1000))
                break
