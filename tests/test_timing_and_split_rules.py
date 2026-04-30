import tkinter as tk
import unittest

from app.ui.gui_app import CustomModelApp
from app.core.timeline_manager import TranscriptManager
from app.ui.ui_block_editor import UIBlockEditor
from app.core.subtitle_cues import build_subtitle_cues, remap_cues_for_merged_ranges, SubtitleRenderStyle, cues_to_srt, cues_to_vtt
from app.media.video_editor import VideoEditor


class DummyPlayer:
    def __init__(self):
        self.time_ms = None
        self.play_calls = 0
        self.live_subtitle_calls = []
        self.clear_live_subtitle_calls = 0
        self.marquee_calls = []
        self.clear_marquee_calls = 0
        self.clear_subtitle_calls = 0

    def set_time(self, ms):
        self.time_ms = ms

    def play(self):
        self.play_calls += 1

    def get_time(self):
        return self.time_ms or 0

    def set_live_subtitle(self, text, *, size=80, color=0xFFFFFF, opacity=255, margin_v=50, font_name=None):
        self.live_subtitle_calls.append(
            {
                "text": text,
                "size": size,
                "color": color,
                "opacity": opacity,
                "margin_v": margin_v,
                "font_name": font_name,
            }
        )
        return True

    def clear_live_subtitle(self):
        self.clear_live_subtitle_calls += 1
        return True

    def clear_subtitle(self):
        self.clear_subtitle_calls += 1
        return True

    def set_marquee(self, text, *, size=80, color=0xFFFFFF, opacity=255, margin_v=50):
        self.marquee_calls.append(
            {"text": text, "size": size, "color": color, "opacity": opacity, "margin_v": margin_v}
        )
        return True

    def clear_marquee(self):
        self.clear_marquee_calls += 1
        return True


class DummyLoopPlayer:
    def __init__(self, *, position=0.0, time_ms=0, length_ms=0, playing=False):
        self._position = position
        self._time_ms = time_ms
        self._length_ms = length_ms
        self._playing = playing

    def sync_video_container(self):
        return None

    def get_position(self):
        return self._position

    def get_time(self):
        return self._time_ms

    def get_length(self):
        return self._length_ms

    def is_playing(self):
        return self._playing


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

    def test_build_subtitle_cues_trims_overlap(self):
        cues = build_subtitle_cues(
            [
                {"s": 1.0, "e": 2.0, "t": "첫 줄"},
                {"s": 2.0, "e": 3.0, "t": "둘째 줄"},
            ]
        )

        self.assertEqual(cues[0].end, 1.99)
        self.assertEqual(cues[1].start, 2.0)

    def test_remap_cues_for_merged_ranges_maps_to_cut_timeline(self):
        cues = build_subtitle_cues(
            [
                {"s": 10.0, "e": 11.0, "t": "첫 줄"},
                {"s": 20.0, "e": 21.0, "t": "둘째 줄"},
            ]
        )

        remapped = remap_cues_for_merged_ranges(cues, [(10.0, 12.0), (20.0, 22.0)])

        self.assertEqual(remapped[0].start, 0.0)
        self.assertEqual(remapped[0].end, 1.0)
        self.assertEqual(remapped[1].start, 2.0)
        self.assertEqual(remapped[1].end, 3.0)

    def test_cue_exports_format_without_ass(self):
        cues = build_subtitle_cues([{"s": 1.0, "e": 2.0, "t": "첫 줄"}])

        srt = cues_to_srt(cues)
        vtt = cues_to_vtt(cues)

        self.assertIn("00:00:01,000 --> 00:00:02,000", srt)
        self.assertIn("WEBVTT", vtt)
        self.assertIn("00:00:01.000 --> 00:00:02.000", vtt)

    def test_video_editor_builds_drawtext_chain_from_cues(self):
        editor = VideoEditor()
        cues = build_subtitle_cues([{"s": 1.0, "e": 2.0, "t": "첫 줄"}])
        style = SubtitleRenderStyle(font_name="Noto Sans KR", font_size=64, margin_v=60)

        import tempfile, os, shutil
        temp_dir = tempfile.mkdtemp(prefix="vibe_drawtext_test_")
        try:
            chain = editor._build_drawtext_filter_chain(cues, style, temp_dir)
            self.assertIn("drawtext=", chain)
            self.assertIn("enable='between(t,1.000,2.000)'", chain)
            self.assertIn("fontsize=64", chain)
            self.assertTrue(os.path.exists(os.path.join(temp_dir, "cue_00000.txt")))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_overlay_preview_uses_active_subtitle_text(self):
        dummy = type("DummyApp", (), {})()
        dummy.results_data = [
            {"s": 1.00, "e": 2.00, "t": "첫 줄"},
            {"s": 2.01, "e": 3.00, "t": "둘째 줄"},
        ]
        dummy._get_subtitle_entries_no_overlap = lambda use_display_start=False: CustomModelApp._get_subtitle_entries_no_overlap(dummy, use_display_start=use_display_start)

        entry = CustomModelApp._get_live_overlay_entry(dummy, 2.5)

        self.assertIsNotNone(entry)
        self.assertEqual(entry["t"], "둘째 줄")

    def test_overlay_preview_returns_none_when_no_active_subtitle(self):
        dummy = type("DummyApp", (), {})()
        dummy.results_data = [
            {"s": 1.00, "e": 2.00, "t": "첫 줄"},
        ]
        dummy._get_subtitle_entries_no_overlap = lambda use_display_start=False: CustomModelApp._get_subtitle_entries_no_overlap(dummy, use_display_start=use_display_start)

        entry = CustomModelApp._get_live_overlay_entry(dummy, 2.5)

        self.assertIsNone(entry)

    def test_apply_preview_subtitles_uses_live_marquee_path(self):
        player = DummyPlayer()
        dummy = type("DummyApp", (), {})()
        dummy.results_data = [{"s": 1.0, "e": 2.0, "t": "첫 줄"}]
        dummy.player = player
        dummy.use_live_overlay_preview = True
        dummy._live_overlay_cache = {}
        dummy.sub_font_size = type("Var", (), {"get": lambda self: 80})()
        dummy.sub_color_f = type("Var", (), {"get": lambda self: "#FFFFFF"})()
        dummy.sub_y_pos = type("Var", (), {"get": lambda self: 50})()
        dummy.sub_font = type("Var", (), {"get": lambda self: "맑은 고딕"})()
        dummy._get_subtitle_entries_no_overlap = lambda use_display_start=False: CustomModelApp._get_subtitle_entries_no_overlap(dummy, use_display_start=use_display_start)
        dummy._get_live_overlay_entry = lambda curr_sec: CustomModelApp._get_live_overlay_entry(dummy, curr_sec)
        dummy._hex_to_vlc_color = lambda hex_color: CustomModelApp._hex_to_vlc_color(dummy, hex_color)
        dummy._apply_live_overlay_for_time = lambda curr_sec, force=False: CustomModelApp._apply_live_overlay_for_time(dummy, curr_sec, force=force)
        player.time_ms = 1500

        CustomModelApp.apply_preview_subtitles(dummy, force_reload=True)

        self.assertEqual(player.clear_subtitle_calls, 0)
        self.assertEqual(player.clear_live_subtitle_calls, 0)
        self.assertEqual(player.clear_marquee_calls, 0)
        self.assertEqual(player.live_subtitle_calls[-1]["text"], "첫 줄")
        self.assertEqual(player.live_subtitle_calls[-1]["font_name"], "맑은 고딕")

    def test_apply_preview_subtitles_clears_live_marquee_when_no_results(self):
        player = DummyPlayer()
        dummy = type("DummyApp", (), {})()
        dummy.results_data = []
        dummy.player = player
        dummy.use_live_overlay_preview = True

        CustomModelApp.apply_preview_subtitles(dummy, force_reload=True)

        self.assertEqual(player.clear_live_subtitle_calls, 1)

    def test_update_loop_handles_unknown_total_length_with_live_overlay(self):
        calls = []
        seek_values = []
        play_states = []

        dummy = type("DummyApp", (), {})()
        dummy.player = DummyLoopPlayer(position=0.2, time_ms=500, length_ms=0, playing=False)
        dummy.is_seeking = False
        dummy.seek_var = type("Var", (), {"set": lambda self, value: seek_values.append(value)})()
        dummy.results_data = []
        dummy.root = type("Root", (), {"after": lambda self, delay, cb: calls.append(("after", delay, cb.__name__))})()
        dummy.btn_play = type("Btn", (), {"config": lambda self, **kwargs: play_states.append(kwargs.get("text"))})()
        dummy.ICON_PLAY = "PLAY"
        dummy.ICON_PAUSE = "PAUSE"
        dummy.use_live_overlay_preview = True
        dummy._apply_live_overlay_for_time = lambda curr_sec: calls.append(("overlay", round(curr_sec, 3)))
        dummy.update_loop = lambda: None

        CustomModelApp.update_loop(dummy)

        self.assertIn(("overlay", 0.5), calls)
        self.assertIn(("after", 16, "<lambda>"), calls)
        self.assertEqual(seek_values, [200.0])
        self.assertEqual(play_states[-1], "PLAY")

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
