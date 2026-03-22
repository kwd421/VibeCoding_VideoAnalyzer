import sys
import time

if sys.platform == "darwin":
    try:
        import objc
        from AppKit import NSApp, NSMakeRect, NSView, NSWindowAbove
    except Exception:
        objc = None
        NSApp = None
        NSMakeRect = None
        NSView = None
        NSWindowAbove = None
else:
    objc = None
    NSApp = None
    NSMakeRect = None
    NSView = None
    NSWindowAbove = None


class MacVideoContainer:
    def __init__(self, canvas_widget):
        self.canvas_widget = canvas_widget
        self._ns_container = None
        self._ns_window = None
        self._ns_content = None

    @property
    def available(self):
        return bool(self.canvas_widget is not None and objc and NSApp and NSMakeRect and NSView)

    def debug_log(self, message):
        if sys.platform != "darwin":
            return
        try:
            with open("/tmp/vibe_video_debug.log", "a", encoding="utf-8") as fp:
                fp.write(f"{time.strftime('%H:%M:%S')} {message}\n")
        except Exception:
            pass

    def attach(self, player):
        if not self.available:
            self.debug_log("attach: unavailable")
            return False
        try:
            self.canvas_widget.update_idletasks()
            app = NSApp()
            if app is None:
                self.debug_log("attach: NSApp unavailable")
                return False
            window = app.keyWindow() or app.mainWindow() or (app.windows()[0] if app.windows() else None)
            if window is None:
                self.debug_log("attach: no window")
                return False
            content = window.contentView()
            if self._ns_container is None or self._ns_window != window:
                if self._ns_container is not None:
                    try:
                        self._ns_container.removeFromSuperview()
                    except Exception:
                        pass
                container = NSView.alloc().initWithFrame_(content.bounds())
                container.setWantsLayer_(True)
                if NSWindowAbove is not None and hasattr(content, "addSubview_positioned_relativeTo_"):
                    content.addSubview_positioned_relativeTo_(container, NSWindowAbove, None)
                else:
                    content.addSubview_(container)
                self._ns_container = container
                self._ns_window = window
                self._ns_content = content
            self.sync()
            player.set_nsobject(objc.pyobjc_id(self._ns_container))
            self.debug_log("attach: set_nsobject ok")
            return True
        except Exception as exc:
            self.debug_log(f"attach_error: {exc}")
            return False

    def sync(self):
        if not self.available or self._ns_container is None or self._ns_content is None:
            return
        try:
            self.canvas_widget.update_idletasks()
            toplevel = self.canvas_widget.winfo_toplevel()
            content_bounds = self._ns_content.bounds()
            content_h = content_bounds.size.height
            x = self.canvas_widget.winfo_rootx() - toplevel.winfo_rootx()
            y = self.canvas_widget.winfo_rooty() - toplevel.winfo_rooty()
            w = self.canvas_widget.winfo_width()
            h = self.canvas_widget.winfo_height()
            if w <= 1 or h <= 1:
                return
            cocoa_y = max(0, content_h - y - h)
            self._ns_container.setFrame_(NSMakeRect(x, cocoa_y, w, h))
            self._ns_container.setHidden_(False)
            self._ns_container.setNeedsDisplay_(True)
            if hasattr(self._ns_container, "displayIfNeeded"):
                self._ns_container.displayIfNeeded()
        except Exception as exc:
            self.debug_log(f"sync_error: {exc}")

    def hide(self):
        if self._ns_container is not None:
            try:
                self._ns_container.setHidden_(True)
            except Exception:
                pass
