        vis_text = '켜짐' if selected.visible else '꺼짐'
        name = selected.text if selected.type in ('text', 'subtitle') else os.path.basename(selected.source or selected.id)
        info_text = (
            f'선택: {name}\n'
            f'유형: {selected.type}\n'
            f'레이어: {selected.layer_index}\n'
            f'표시: {vis_text}'
        )
        overlap_hint = getattr(self, '_overlay_timeline_overlap_hint', None)
        if overlap_hint and overlap_hint.get('item_id') == selected.id and overlap_hint.get('count', 1) > 1:
            info_text += (
                f"\n겹침 후보: {overlap_hint['index']}/{overlap_hint['count']} "
                f"(Shift+클릭 / 반복 클릭)"
            )
        self.lbl_overlay_props.config(text=info_text)
