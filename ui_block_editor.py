import tkinter as tk
from tkinter import ttk

class UIBlockEditor:
    """[시니어 UI 분리] 단어 블록 마법진(Drag & Drop) 캔버스 관리"""
    
    @staticmethod
    def format_time(t_sec):
        m = int(t_sec // 60)
        s = t_sec % 60
        return f"{m:02d}:{s:05.2f}"

    def __init__(self, parent, root, transcript_manager, player, on_tree_rebuild_request):
        self.parent = parent
        self.root = root
        self.transcript_manager = transcript_manager
        self.player = player
        self.on_tree_rebuild_request = on_tree_rebuild_request
        
        self.block_canvas = tk.Canvas(parent, bg="#2c3e50", highlightthickness=0)
        self.block_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sc = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.block_canvas.yview)
        sc.pack(side=tk.RIGHT, fill=tk.Y)
        self.block_canvas.configure(yscrollcommand=sc.set)

        self.block_canvas.bind("<ButtonPress-1>", self.on_block_press)
        self.block_canvas.bind("<B1-Motion>", self.on_block_drag)
        self.block_canvas.bind("<ButtonRelease-1>", self.on_block_release)
        self.block_canvas.bind("<Double-1>", self.on_block_double)
        
        self.parent.bind("<Enter>", lambda e: self.block_canvas.bind_all("<MouseWheel>", self.on_block_scroll))
        self.parent.bind("<Leave>", lambda e: self.block_canvas.unbind_all("<MouseWheel>"))
        self.block_canvas.bind("<Button-3>", self.on_block_right_click)

        self.block_menu = tk.Menu(self.root, tearoff=0)
        self.block_menu.add_command(label="[분리] 현재 단어부터 다음 줄로 나누기", command=self.split_word_block)
        
        self.row_menu = tk.Menu(self.root, tearoff=0)
        self.row_menu.add_command(label="[병합] 위 대사와 합치기", command=lambda: self.merge_row_block(-1))
        self.row_menu.add_command(label="[병합] 아래 대사와 합치기", command=lambda: self.merge_row_block(1))

        self.drag_data = {"items": [], "idx": -1, "w_idx": -1, "start_x": 0, "start_y": 0}
        self.row_y_map = []
        self.action_data = {}

    def on_block_scroll(self, event):
        self.block_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def rebuild_tree_and_render(self):
        # 트리뷰 갱신 요청을 부모에게 전달
        self.on_tree_rebuild_request()
        self.render_block_view()

    def on_block_right_click(self, event):
        x, y = self.block_canvas.canvasx(event.x), self.block_canvas.canvasy(event.y)
        item = self.block_canvas.find_withtag("current")
        if not item: return
        tags = self.block_canvas.gettags(item[0])
        
        word_tag = next((t for t in tags if "_" in t and not t.startswith("row_") and t not in ["current", "word_block"]), None)
        if word_tag:
            try:
                idx, w_idx = map(int, word_tag.split("_"))
                self.action_data = {"idx": idx, "w_idx": w_idx}
                self.block_menu.post(event.x_root, event.y_root)
            except: pass
        else:
            row_tag = next((t for t in tags if str(t).startswith("row_")), None)
            if row_tag:
                try:
                    idx = int(row_tag.split("_")[1])
                    self.action_data = {"idx": idx}
                    self.row_menu.post(event.x_root, event.y_root)
                except: pass

    def split_word_block(self):
        idx, w_idx = self.action_data.get("idx"), self.action_data.get("w_idx")
        if idx is None or w_idx is None: return
        results_data = self.transcript_manager.get_all()
        words = results_data[idx].get('words', [])
        if not words or w_idx == 0 or w_idx >= len(words): return
        
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

    def merge_row_block(self, direction):
        idx = self.action_data.get("idx")
        if idx is None: return
        results_data = self.transcript_manager.get_all()
        target_idx = idx + direction
        if target_idx < 0 or target_idx >= len(results_data): return
        
        base_idx = min(idx, target_idx)
        merge_idx = max(idx, target_idx)
        
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

    def render_block_view(self):
        if not hasattr(self, 'block_canvas') or not self.block_canvas.winfo_exists(): return
        self.block_canvas.delete("all")
        y_offset = 15
        self.row_y_map = []
        results_data = self.transcript_manager.get_all()
        
        for idx, r in enumerate(results_data):
            row_id = self.block_canvas.create_rectangle(10, y_offset, 2500, y_offset + 35, fill="#34495e", outline="", tags=f"row_{idx}")
            self.block_canvas.tag_lower(row_id)
            
            self.block_canvas.create_text(20, y_offset + 17, text=f"[{idx+1}]", fill="#bdc3c7", anchor=tk.W, font=("", 9))
            
            start_txt = self.block_canvas.create_text(50, y_offset + 17, text=self.format_time(r.get('s',0)), fill="#3498db", anchor=tk.W, font=("", 9, "underline"))
            self.block_canvas.tag_bind(start_txt, "<Button-1>", lambda e, s=r.get('s',0): self.player.set_time(int(s * 1000)))
            
            self.block_canvas.create_text(100, y_offset + 17, text="-", fill="#ecf0f1", anchor=tk.W, font=("", 9))
            
            end_txt = self.block_canvas.create_text(115, y_offset + 17, text=self.format_time(r.get('e',0)), fill="#e74c3c", anchor=tk.W, font=("", 9, "underline"))
            self.block_canvas.tag_bind(end_txt, "<Button-1>", lambda e, s=r.get('e',0): self.player.set_time(int(s * 1000)))
            
            x_offset = 180
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
            
            results_data[idx]['words'] = words

            for w_idx, w_obj in enumerate(words):
                text = w_obj['word']
                text_id = self.block_canvas.create_text(x_offset + 10, y_offset + 17, text=text, fill="#2c3e50", anchor=tk.W, font=("", 10, "bold"))
                bbox = self.block_canvas.bbox(text_id)
                if bbox:
                    w_width = bbox[2] - bbox[0] + 20
                    rect_id = self.block_canvas.create_rectangle(x_offset, y_offset + 3, x_offset + w_width, y_offset + 32, fill="#f1c40f", outline="#e67e22", width=2, tags=("word_block", f"{idx}_{w_idx}"))
                    self.block_canvas.tag_lower(rect_id, text_id)
                    self.block_canvas.addtag_withtag(f"{idx}_{w_idx}", text_id)
                    x_offset += w_width + 8
            
            self.row_y_map.append({'idx': idx, 'y_start': y_offset, 'y_end': y_offset + 35})
            y_offset += 45
            
        self.block_canvas.configure(scrollregion=(0, 0, 2500, y_offset + 20))

    def on_block_press(self, event):
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
            
            items = self.block_canvas.find_withtag(word_tag)
            self.drag_data["items"] = items
            for it in items:
                self.block_canvas.tag_raise(it)
        except: pass

    def on_block_drag(self, event):
        if not getattr(self, 'drag_data', {}).get("items"): return
        x, y = self.block_canvas.canvasx(event.x), self.block_canvas.canvasy(event.y)
        dx = x - self.drag_data["start_x"]
        dy = y - self.drag_data["start_y"]
        for it in self.drag_data["items"]:
            self.block_canvas.move(it, dx, dy)
        self.drag_data["start_x"] = x
        self.drag_data["start_y"] = y
        
        target = None
        for rmap in self.row_y_map:
            if rmap['y_start'] <= y <= rmap['y_end']:
                target = {'type': 'merge', 'idx': rmap['idx']}
                break
        if target is None:
            for rmap in self.row_y_map:
                if rmap['y_start'] - 10 <= y < rmap['y_start']:
                    target = {'type': 'insert', 'idx': rmap['idx']}
                    break
                elif rmap['y_end'] < y <= rmap['y_end'] + 10:
                    target = {'type': 'insert', 'idx': rmap['idx'] + 1}
                    break

        self.block_canvas.delete("drop_highlight")
        if target is not None:
            s_idx = self.drag_data["idx"]
            w_idx = self.drag_data["w_idx"]
            results_data = self.transcript_manager.get_all()
            n_words = len(results_data[s_idx].get('words', []))
            
            is_valid = False
            if target['type'] == 'merge':
                target_idx = target['idx']
                if target_idx == s_idx:
                    is_valid = True
                elif target_idx == s_idx - 1 and w_idx == 0:
                    is_valid = True
                elif target_idx == s_idx + 1 and w_idx == n_words - 1:
                    is_valid = True
            elif target['type'] == 'insert':
                insert_idx = target['idx']
                if insert_idx == s_idx and w_idx == 0:
                    is_valid = True
                elif insert_idx == s_idx + 1 and w_idx == n_words - 1:
                    is_valid = True
                if n_words <= 1:
                    is_valid = False
                
            if is_valid:
                if target['type'] == 'merge':
                    rmap = next(r for r in self.row_y_map if r['idx'] == target['idx'])
                    self.block_canvas.create_rectangle(10, rmap['y_start'] - 2, 2500, rmap['y_end'] + 2, fill="", outline="#e74c3c", width=2, dash=(4,4), tags="drop_highlight")
                elif target['type'] == 'insert':
                    insert_idx = target['idx']
                    if insert_idx < len(self.row_y_map):
                        rmap = self.row_y_map[insert_idx]
                        y_pos = rmap['y_start'] - 8
                    else:
                        rmap = self.row_y_map[-1]
                        y_pos = rmap['y_end'] + 8
                    self.block_canvas.create_line(10, y_pos, 2500, y_pos, fill="#f1c40f", width=3, dash=(4,4), tags="drop_highlight")
                self.block_canvas.tag_lower("drop_highlight")

    def on_block_release(self, event):
        if not getattr(self, 'drag_data', {}).get("items"): return
        y = self.block_canvas.canvasy(event.y)
        target = None
        for rmap in self.row_y_map:
            if rmap['y_start'] <= y <= rmap['y_end']:
                target = {'type': 'merge', 'idx': rmap['idx']}
                break
        if target is None:
            for rmap in self.row_y_map:
                if rmap['y_start'] - 10 <= y < rmap['y_start']:
                    target = {'type': 'insert', 'idx': rmap['idx']}
                    break
                elif rmap['y_end'] < y <= rmap['y_end'] + 10:
                    target = {'type': 'insert', 'idx': rmap['idx'] + 1}
                    break
                
        if target is not None:
            s_idx = self.drag_data["idx"]
            w_idx = self.drag_data["w_idx"]
            results_data = self.transcript_manager.get_all()
            n_words = len(results_data[s_idx].get('words', []))
            
            is_valid = False
            if target['type'] == 'merge':
                target_idx = target['idx']
                if target_idx == s_idx:
                    is_valid = True
                elif target_idx == s_idx - 1 and w_idx == 0:
                    is_valid = True
                elif target_idx == s_idx + 1 and w_idx == n_words - 1:
                    is_valid = True
            elif target['type'] == 'insert':
                insert_idx = target['idx']
                if insert_idx == s_idx and w_idx == 0:
                    is_valid = True
                elif insert_idx == s_idx + 1 and w_idx == n_words - 1:
                    is_valid = True
                if n_words <= 1:
                    is_valid = False
                
            if not is_valid or (target['type'] == 'merge' and target['idx'] == s_idx):
                if not is_valid:
                    self.block_canvas.delete("drop_highlight")
                    self.drag_data = {"items": []}
                    self.render_block_view()
                    return
            else:
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
                self.player.set_time(int(r.get('s', 0) * 1000))
                break
