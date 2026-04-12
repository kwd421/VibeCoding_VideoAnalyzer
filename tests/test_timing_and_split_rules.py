import tkinter as tk
import unittest

from gui_app import CustomModelApp
from timeline_manager import TranscriptManager
from ui_block_editor import UIBlockEditor


class DummyPlayer:
    def __init__(self):
        self.time_ms = None
        self.play_calls = 0

    def set_time(self, ms):
        self.time_ms = ms

    def play(self):
        self.play_calls += 1


class TimingAndSplitRulesTests(unittest.TestCase):
    def test_has_option_modifier_supports_mac_mousewheel_state(self):
        event = type("Evt", (), {"state": 0x4 | 0x10})()
        legacy_event = type("Evt", (), {"state": 0x4 | 0x8})()

        self.assertTrue(UIBlockEditor.has_option_modifier(event))
        self.assertTrue(UIBlockEditor.has_option_modifier(legacy_event))

    def test_subtitle_entries_use_segment_start_even_when_words_start_later(self):
        dummy = type("DummyApp", (), {})()
        dummy.results_data = [
            {
                "s": 1.00,
                "e": 2.00,
                "t": "테스트 문장",
                "words": [
                    {"word": "어", "s": 1.00, "e": 1.05},
                    {"word": "테스트", "s": 1.40, "e": 1.70},
                ],
            }
        ]

        entries = CustomModelApp._get_subtitle_entries_no_overlap(dummy, use_display_start=True)

        self.assertEqual(entries[0]["s"], 1.00)

    def test_manual_start_timing_uses_segment_start_for_subtitles(self):
        dummy = type("DummyApp", (), {})()
        dummy.results_data = [
            {
                "s": 5.00,
                "e": 6.00,
                "t": "테스트 문장",
                "words": [
                    {"word": "어", "s": 5.00, "e": 5.10},
                    {"word": "테스트", "s": 5.40, "e": 5.70},
                ],
                "_manual_start_timing": True,
            }
        ]

        entries = CustomModelApp._get_subtitle_entries_no_overlap(dummy, use_display_start=True)

        self.assertEqual(entries[0]["s"], 5.00)

    def test_smart_split_text_never_exceeds_max_chars(self):
        manager = TranscriptManager()
        text = "a cccccc"

        chunks = manager.smart_split_text(text, 5)

        self.assertTrue(chunks)
        self.assertTrue(all(len(chunk) <= 5 for chunk in chunks), chunks)

    def test_word_inline_edit_claims_focus_immediately(self):
        root = tk.Tk()
        root.geometry("800x400")
        frame = tk.Frame(root)
        frame.pack(fill="both", expand=True)

        manager = TranscriptManager()
        manager.results_data = [
            {
                "s": 1.0,
                "e": 2.0,
                "t": "안녕 하세요",
                "words": [
                    {"word": "안녕", "s": 1.0, "e": 1.4},
                    {"word": "하세요", "s": 1.4, "e": 2.0},
                ],
            }
        ]

        editor = UIBlockEditor(frame, root, manager, lambda: None, lambda fast=False: None)
        editor.render_block_view()
        root.update()

        editor._edit_word_inline(0, 0)
        root.update()
        root.update_idletasks()

        self.assertIs(root.focus_get(), editor.active_entry)
        root.destroy()

    def test_word_inline_edit_uses_placeholder_selected_look_on_open(self):
        root = tk.Tk()
        root.geometry("800x400")
        frame = tk.Frame(root)
        frame.pack(fill="both", expand=True)

        manager = TranscriptManager()
        manager.results_data = [
            {
                "s": 1.0,
                "e": 2.0,
                "t": "안녕 하세요",
                "words": [
                    {"word": "안녕", "s": 1.0, "e": 1.4},
                    {"word": "하세요", "s": 1.4, "e": 2.0},
                ],
            }
        ]

        editor = UIBlockEditor(frame, root, manager, lambda: None, lambda fast=False: None)
        editor.render_block_view()
        root.update()

        editor._edit_word_inline(0, 0)
        root.update()
        root.update_idletasks()

        self.assertFalse(editor.active_entry.selection_present())
        self.assertTrue(getattr(editor.active_entry, "_placeholder_active", False))
        self.assertEqual(editor.active_entry.get(), "")
        root.destroy()

    def test_word_inline_edit_saves_on_keyrelease_return(self):
        root = tk.Tk()
        root.geometry("800x400")
        frame = tk.Frame(root)
        frame.pack(fill="both", expand=True)

        manager = TranscriptManager()
        manager.results_data = [
            {
                "s": 1.0,
                "e": 2.0,
                "t": "안녕 하세요",
                "words": [
                    {"word": "안녕", "s": 1.0, "e": 1.4},
                    {"word": "하세요", "s": 1.4, "e": 2.0},
                ],
            }
        ]

        editor = UIBlockEditor(frame, root, manager, lambda: None, lambda fast=False: None)
        editor.render_block_view()
        root.update()

        editor._edit_word_inline(0, 0)
        root.update()
        root.update_idletasks()

        editor.active_entry.delete(0, tk.END)
        editor.active_entry.insert(0, "새단어")
        editor.active_entry.event_generate("<KeyRelease-Return>")
        root.update()
        root.update_idletasks()

        self.assertIsNone(editor.active_entry)
        self.assertEqual(manager.results_data[0]["words"][0]["word"], "새단어")
        root.destroy()

    def test_word_inline_first_input_hides_placeholder_and_clears_existing_text(self):
        root = tk.Tk()
        root.geometry("800x400")
        frame = tk.Frame(root)
        frame.pack(fill="both", expand=True)

        manager = TranscriptManager()
        manager.results_data = [
            {
                "s": 1.0,
                "e": 2.0,
                "t": "안녕 하세요",
                "words": [
                    {"word": "안녕", "s": 1.0, "e": 1.4},
                    {"word": "하세요", "s": 1.4, "e": 2.0},
                ],
            }
        ]

        editor = UIBlockEditor(frame, root, manager, lambda: None, lambda fast=False: None)
        editor.render_block_view()
        root.update()

        editor._edit_word_inline(0, 0)
        root.update()
        root.update_idletasks()

        placeholder = editor.active_entry._placeholder_widget
        event = type("Evt", (), {"keysym": "a", "char": "a", "state": 0})()
        editor._handle_initial_inline_keypress(editor.active_entry, placeholder, event)

        self.assertFalse(getattr(editor.active_entry, "_placeholder_active", True))
        self.assertEqual(editor.active_entry.get(), "")
        root.destroy()

    def test_word_inline_navigation_restores_original_text(self):
        root = tk.Tk()
        root.geometry("800x400")
        frame = tk.Frame(root)
        frame.pack(fill="both", expand=True)

        manager = TranscriptManager()
        manager.results_data = [
            {
                "s": 1.0,
                "e": 2.0,
                "t": "안녕 하세요",
                "words": [
                    {"word": "안녕", "s": 1.0, "e": 1.4},
                    {"word": "하세요", "s": 1.4, "e": 2.0},
                ],
            }
        ]

        editor = UIBlockEditor(frame, root, manager, lambda: None, lambda fast=False: None)
        editor.render_block_view()
        root.update()

        editor._edit_word_inline(0, 0)
        root.update()
        root.update_idletasks()

        placeholder = editor.active_entry._placeholder_widget
        event = type("Evt", (), {"keysym": "Left", "char": "", "state": 0})()
        editor._handle_initial_inline_keypress(editor.active_entry, placeholder, event)

        self.assertFalse(getattr(editor.active_entry, "_placeholder_active", True))
        self.assertEqual(editor.active_entry.get(), "안녕")
        root.destroy()

    def test_word_context_menu_uses_click_position_without_current_tag(self):
        root = tk.Tk()
        root.geometry("800x400")
        frame = tk.Frame(root)
        frame.pack(fill="both", expand=True)

        manager = TranscriptManager()
        manager.results_data = [
            {
                "s": 1.0,
                "e": 2.0,
                "t": "안녕 하세요",
                "words": [
                    {"word": "안녕", "s": 1.0, "e": 1.4},
                    {"word": "하세요", "s": 1.4, "e": 2.0},
                ],
            }
        ]

        editor = UIBlockEditor(frame, root, manager, lambda: None, lambda fast=False: None)
        editor.render_block_view()
        root.update()

        shown = {}
        editor.block_menu.tk_popup = lambda x, y: shown.update({"x": x, "y": y})
        editor.block_menu.grab_release = lambda: shown.update({"released": True})

        bbox = editor.block_canvas.bbox("0_0")
        x = int((bbox[0] + bbox[2]) / 2)
        y = int((bbox[1] + bbox[3]) / 2)
        event = type("Evt", (), {"x": x, "y": y, "x_root": 123, "y_root": 456})()

        editor.on_block_right_click(event)

        self.assertEqual(editor.action_data, {"idx": 0, "w_idx": 0})
        self.assertEqual(shown.get("x"), 123)
        self.assertEqual(shown.get("y"), 456)
        self.assertTrue(shown.get("released"))
        root.destroy()

    def test_time_cell_whitespace_click_jumps_to_end_time(self):
        root = tk.Tk()
        root.geometry("800x400")
        frame = tk.Frame(root)
        frame.pack(fill="both", expand=True)

        manager = TranscriptManager()
        manager.results_data = [
            {
                "s": 1.0,
                "e": 2.5,
                "t": "안녕 하세요",
                "words": [
                    {"word": "안녕", "s": 1.0, "e": 1.4},
                    {"word": "하세요", "s": 1.4, "e": 2.5},
                ],
            }
        ]
        player = DummyPlayer()

        editor = UIBlockEditor(frame, root, manager, lambda: player, lambda fast=False: None)
        editor.render_block_view()
        root.update()

        row = editor.row_y_map[0]
        y = int((row["y_start"] + row["y_end"]) / 2)
        x = 220  # 종료시간 셀 여백
        press = type("Evt", (), {"x": x, "y": y})()
        release = type("Evt", (), {"x": x, "y": y})()

        editor.on_block_press(press)
        editor.on_block_release(release)

        self.assertEqual(player.time_ms, 2500)
        self.assertEqual(player.play_calls, 1)
        root.destroy()

    def test_time_text_uses_shared_release_handler_not_direct_click_binding(self):
        root = tk.Tk()
        root.geometry("800x400")
        frame = tk.Frame(root)
        frame.pack(fill="both", expand=True)

        manager = TranscriptManager()
        manager.results_data = [
            {
                "s": 1.0,
                "e": 2.5,
                "t": "안녕 하세요",
                "words": [
                    {"word": "안녕", "s": 1.0, "e": 1.4},
                    {"word": "하세요", "s": 1.4, "e": 2.5},
                ],
            }
        ]
        editor = UIBlockEditor(frame, root, manager, lambda: None, lambda fast=False: None)
        editor.render_block_view()
        root.update()

        start_items = editor.block_canvas.find_withtag("time_s_0")
        end_items = editor.block_canvas.find_withtag("time_e_0")

        self.assertTrue(start_items)
        self.assertTrue(end_items)
        self.assertEqual(editor.block_canvas.tag_bind(start_items[0], "<Button-1>"), "")
        self.assertEqual(editor.block_canvas.tag_bind(end_items[0], "<Button-1>"), "")
        root.destroy()

    def test_ctrl_option_wheel_on_end_time_moves_next_start_together(self):
        root = tk.Tk()
        root.geometry("800x400")
        frame = tk.Frame(root)
        frame.pack(fill="both", expand=True)

        manager = TranscriptManager()
        manager.results_data = [
            {
                "s": 1.0,
                "e": 2.5,
                "t": "첫 줄",
                "words": [{"word": "첫줄", "s": 1.0, "e": 2.5}],
            },
            {
                "s": 2.5,
                "e": 4.0,
                "t": "둘째 줄",
                "words": [{"word": "둘째줄", "s": 2.5, "e": 4.0}],
            },
        ]
        player = DummyPlayer()

        editor = UIBlockEditor(frame, root, manager, lambda: player, lambda fast=False: None)
        editor.render_block_view()
        root.update()

        row = editor.row_y_map[0]
        event = type("Evt", (), {"x": 220, "y": int((row["y_start"] + row["y_end"]) / 2), "delta": -120, "state": 0x4 | 0x10})()

        editor.on_block_scroll(event)

        self.assertEqual(manager.results_data[0]["e"], 2.55)
        self.assertEqual(manager.results_data[1]["s"], 2.55)
        self.assertEqual(player.time_ms, 2550)
        self.assertEqual(player.play_calls, 1)
        root.destroy()

    def test_ctrl_option_wheel_on_start_time_moves_prev_end_together(self):
        root = tk.Tk()
        root.geometry("800x400")
        frame = tk.Frame(root)
        frame.pack(fill="both", expand=True)

        manager = TranscriptManager()
        manager.results_data = [
            {
                "s": 1.0,
                "e": 2.5,
                "t": "첫 줄",
                "words": [{"word": "첫줄", "s": 1.0, "e": 2.5}],
            },
            {
                "s": 2.5,
                "e": 4.0,
                "t": "둘째 줄",
                "words": [{"word": "둘째줄", "s": 2.5, "e": 4.0}],
            },
        ]
        player = DummyPlayer()

        editor = UIBlockEditor(frame, root, manager, lambda: player, lambda fast=False: None)
        editor.render_block_view()
        root.update()

        row = editor.row_y_map[1]
        event = type("Evt", (), {"x": 90, "y": int((row["y_start"] + row["y_end"]) / 2), "delta": 120, "state": 0x4 | 0x10})()

        editor.on_block_scroll(event)

        self.assertEqual(manager.results_data[0]["e"], 2.45)
        self.assertEqual(manager.results_data[1]["s"], 2.45)
        self.assertEqual(player.time_ms, 2450)
        self.assertEqual(player.play_calls, 1)
        root.destroy()


if __name__ == "__main__":
    unittest.main()
