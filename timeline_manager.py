import copy
from typing import List, Dict, Any, Callable
from config_models import TranscriptSegment

class TranscriptManager:
    """[시니어 상태 관리] 전체 트랜스크립트 딕셔너리 리스트 상태를 관리하는 중앙 통제소"""
    def __init__(self):
        self.results_data: List[Dict[str, Any]] = []
        self.undo_stack: List[List[Dict[str, Any]]] = []
        self.redo_stack: List[List[Dict[str, Any]]] = []

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.results_data = []

    def save_state(self):
        """현재 상태를 undo 스택에 저장 (최대 50개)"""
        if len(self.undo_stack) >= 50:
            self.undo_stack.pop(0)
        self.undo_stack.append(copy.deepcopy(self.results_data))
        self.redo_stack.clear()

    def undo(self) -> bool:
        """이전 상태로 되돌리기"""
        if not self.undo_stack: return False
        self.redo_stack.append(copy.deepcopy(self.results_data))
        self.results_data = self.undo_stack.pop()
        return True

    def redo(self) -> bool:
        """실행 취소한 상태를 다시 복구하기"""
        if not self.redo_stack: return False
        self.undo_stack.append(copy.deepcopy(self.results_data))
        self.results_data = self.redo_stack.pop()
        return True

    def get_all(self):
        return self.results_data
        
    def smart_split_text(self, text: str, max_chars: int) -> List[str]:
        """긴 텍스트를 화면 길이에 맞춰 자연스럽게 분할합니다."""
        clean_text = text.strip()
        if len(clean_text) <= max_chars:
            return [clean_text]

        chunks = []
        words = clean_text.split(' ')
        current_chunk = []
        current_len = 0

        for word in words:
            if len(word) > max_chars:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk, current_len = [], 0
                for i in range(0, len(word), max_chars):
                    chunks.append(word[i:i+max_chars])
                continue

            if current_len + len(word) + (1 if current_chunk else 0) > max_chars:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_len = len(word)
            else:
                current_chunk.append(word)
                current_len += len(word) + (1 if current_chunk else 0)
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
            
        if len(chunks) > 1:
            last = chunks[-1]
            prev = chunks[-2]
            if len(last.replace(" ", "")) < max(3, int(max_chars * 0.4)) and len(prev) + len(last) + 1 <= max_chars:
                chunks[-2] = prev + " " + last
                chunks.pop()
                
        return chunks

    def add_segment(self, r: dict, ui_callback: Callable[[dict], None]):
        """타임라인 겹침 방어 등의 전처리 후 결과 데이터 삽입"""
        if self.results_data:
            prev = self.results_data[-1]
            last_e = prev['e']
            if r['e'] <= last_e:
                return
            if r['s'] <= last_e:
                new_prev_e = round(max(prev['s'], r['s'] - 0.01), 3)
                if new_prev_e != prev['e']:
                    prev['e'] = new_prev_e
                    words = prev.get('words', [])
                    if words:
                        last_word = words[-1]
                        if last_word['e'] > new_prev_e:
                            last_word['e'] = max(last_word['s'], new_prev_e)
                    if prev['t'].endswith('s') and ' ' not in prev['t'] and '[' not in prev['t']:
                        prev['t'] = f"{(prev['e'] - prev['s']):.2f}s"
                    ui_callback({
                        "action": "update_row",
                        "i": len(self.results_data),
                        "s": prev['s'],
                        "e": prev['e'],
                        "t": prev['t'],
                    })
            
        if r['t'].endswith('s') and ' ' not in r['t'] and '[' not in r['t']:
            r['t'] = f"{(r['e'] - r['s']):.2f}s"
            
        self.results_data.append(r)
        
        ui_callback({"action": "add_row", "i": len(self.results_data), "s": r['s'], "e": r['e'], "t": r['t']})
