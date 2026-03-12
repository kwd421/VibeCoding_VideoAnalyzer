from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional
import uuid


OverlayType = Literal["image", "text", "subtitle", "audio", "effect"]


@dataclass
class OverlayItem:
    id: str
    type: OverlayType
    start_time: float
    end_time: float
    track_index: int
    layer_index: int = 0
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    rotation: float = 0.0
    opacity: float = 1.0
    visible: bool = True
    source: Optional[str] = None
    text: Optional[str] = None
    font_size: float = 48.0
    text_color: str = '#FFFFFF'
    text_align: str = 'left'
    extra: Dict[str, object] = field(default_factory=dict)


@dataclass
class TimelineTrack:
    id: str
    name: str
    kind: Literal["overlay", "subtitle", "audio", "effect"] = "overlay"
    items: List[OverlayItem] = field(default_factory=list)


class OverlayManager:
    def __init__(self, render_width: int = 1920, render_height: int = 1080):
        self.render_width = render_width
        self.render_height = render_height
        self.selected_item_id: Optional[str] = None
        self.tracks: List[TimelineTrack] = [
            TimelineTrack(id="overlay-track-1", name="Overlay 1", kind="overlay")
        ]

    def create_image_overlay(
        self,
        source: str,
        start_time: float,
        end_time: float,
        x: float = 120.0,
        y: float = 120.0,
        width: float = 320.0,
        height: float = 180.0,
        track_index: int = 0,
    ) -> OverlayItem:
        item = OverlayItem(
            id=f"overlay-{uuid.uuid4().hex[:8]}",
            type="image",
            start_time=start_time,
            end_time=end_time,
            track_index=track_index,
            layer_index=len(self.tracks[track_index].items) if track_index < len(self.tracks) else 0,
            x=x,
            y=y,
            width=width,
            height=height,
            source=source,
        )
        self.add_item(item)
        return item

    def create_text_overlay(
        self,
        text_value: str,
        start_time: float,
        end_time: float,
        x: float = 120.0,
        y: float = 120.0,
        width: float = 360.0,
        height: float = 120.0,
        track_index: int = 0,
        font_size: float = 64.0,
        text_color: str = '#FFFFFF',
        text_align: str = 'left',
    ) -> OverlayItem:
        item = OverlayItem(
            id=f"overlay-{uuid.uuid4().hex[:8]}",
            type="text",
            text=text_value,
            start_time=start_time,
            end_time=end_time,
            track_index=track_index,
            layer_index=len(self.tracks[track_index].items) if track_index < len(self.tracks) else 0,
            x=x,
            y=y,
            width=width,
            height=height,
            font_size=font_size,
            text_color=text_color,
            text_align=text_align,
        )
        self.add_item(item)
        return item

    def add_item(self, item: OverlayItem):
        while item.track_index >= len(self.tracks):
            next_idx = len(self.tracks) + 1
            self.tracks.append(
                TimelineTrack(
                    id=f"overlay-track-{next_idx}",
                    name=f"Overlay {next_idx}",
                    kind="overlay",
                )
            )
        self.tracks[item.track_index].items.append(item)


    def remove_item(self, item_id: str) -> bool:
        for track in self.tracks:
            for idx, item in enumerate(track.items):
                if item.id == item_id:
                    track.items.pop(idx)
                    if self.selected_item_id == item_id:
                        self.selected_item_id = None
                    self.normalize_track_layers(item.track_index)
                    return True
        return False

    def get_all_items(self) -> List[OverlayItem]:
        items: List[OverlayItem] = []
        for track in self.tracks:
            items.extend(track.items)
        return items

    def get_visible_items(self, time_sec: float) -> List[OverlayItem]:
        items = [
            item
            for item in self.get_all_items()
            if item.visible and item.start_time <= time_sec <= item.end_time
        ]
        return sorted(items, key=lambda x: (x.track_index, x.layer_index))

    def get_item(self, item_id: str) -> Optional[OverlayItem]:
        for item in self.get_all_items():
            if item.id == item_id:
                return item
        return None

    def set_selected(self, item_id: Optional[str]):
        self.selected_item_id = item_id

    def get_selected(self) -> Optional[OverlayItem]:
        if not self.selected_item_id:
            return None
        return self.get_item(self.selected_item_id)

    def _track_items_sorted(self, track_index: int) -> List[OverlayItem]:
        if track_index < 0 or track_index >= len(self.tracks):
            return []
        return sorted(self.tracks[track_index].items, key=lambda item: (item.layer_index, item.id))

    def normalize_track_layers(self, track_index: int):
        for idx, item in enumerate(self._track_items_sorted(track_index)):
            item.layer_index = idx

    def move_selected_layer(self, direction: str) -> bool:
        selected = self.get_selected()
        if selected is None:
            return False
        items = self._track_items_sorted(selected.track_index)
        if len(items) <= 1:
            return False
        try:
            idx = next(i for i, item in enumerate(items) if item.id == selected.id)
        except StopIteration:
            return False
        new_idx = idx
        if direction == 'forward':
            new_idx = min(len(items) - 1, idx + 1)
        elif direction == 'backward':
            new_idx = max(0, idx - 1)
        elif direction == 'front':
            new_idx = len(items) - 1
        elif direction == 'back':
            new_idx = 0
        else:
            return False
        if new_idx == idx:
            return False
        item = items.pop(idx)
        items.insert(new_idx, item)
        for layer_idx, overlay in enumerate(items):
            overlay.layer_index = layer_idx
        return True

    def preview_rect(self, item: OverlayItem, preview_w: int, preview_h: int):
        sx = preview_w / max(1, self.render_width)
        sy = preview_h / max(1, self.render_height)
        return (
            item.x * sx,
            item.y * sy,
            item.width * sx,
            item.height * sy,
        )

    def update_item_from_preview_rect(
        self,
        item: OverlayItem,
        x: float,
        y: float,
        width: float,
        height: float,
        preview_w: int,
        preview_h: int,
    ):
        sx = self.render_width / max(1, preview_w)
        sy = self.render_height / max(1, preview_h)
        item.x = max(0.0, x * sx)
        item.y = max(0.0, y * sy)
        item.width = max(16.0, width * sx)
        item.height = max(16.0, height * sy)
