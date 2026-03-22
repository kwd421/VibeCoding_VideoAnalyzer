from .video_player_common import attach_non_macos_player


def attach_player(player, canvas_id):
    attach_non_macos_player(player, canvas_id)
