import io
import base64
from typing import Optional, Tuple, Dict, Any
from PIL import Image
import mss
from config_manager import ConfigManager


def capture_screen_jpeg(
    max_width: int = 1440,
    quality: int = 82,
    crop_rect: Optional[Dict[str, int]] = None
) -> Optional[Tuple[bytes, str]]:
    """
    Capture the desktop screen according to user's capture_mode setting:
      - primary: Primary monitor (sct.monitors[1])
      - all_screens: All monitors combined (sct.monitors[0])
      - monitor_2: Secondary monitor if available
      - active_window: Crop to the active foreground window (across any monitor)
      - custom_region: Crop to user-selected [left, top, width, height]
    Returns: (jpeg_bytes, base64_str) or None on failure.
    """
    try:
        cfg = ConfigManager()
        mode = cfg.get("capture_mode", "primary").strip()
        custom_rect = cfg.get("custom_capture_rect", [])

        with mss.mss() as sct:
            virtual_all = sct.monitors[0]

            if mode == "all_screens":
                sct_img = sct.grab(virtual_all)
            elif mode == "monitor_2" and len(sct.monitors) > 2:
                sct_img = sct.grab(sct.monitors[2])
            elif mode == "custom_region" and isinstance(custom_rect, list) and len(custom_rect) == 4:
                lx, ty, rw, rh = [int(v) for v in custom_rect]
                if rw > 20 and rh > 20:
                    sct_img = sct.grab({"left": lx, "top": ty, "width": rw, "height": rh})
                else:
                    sct_img = sct.grab(sct.monitors[1])
            elif mode == "active_window" and crop_rect and crop_rect.get("width", 0) > 100 and crop_rect.get("height", 0) > 100:
                left = max(virtual_all["left"], crop_rect["left"])
                top = max(virtual_all["top"], crop_rect["top"])
                right = min(virtual_all["left"] + virtual_all["width"], crop_rect["left"] + crop_rect["width"])
                bottom = min(virtual_all["top"] + virtual_all["height"], crop_rect["top"] + crop_rect["height"])
                w = right - left
                h = bottom - top
                if w > 80 and h > 80:
                    sct_img = sct.grab({"left": left, "top": top, "width": w, "height": h})
                else:
                    sct_img = sct.grab(sct.monitors[1])
            else:
                # Default: primary monitor, or crop_rect if explicitly passed
                monitor = sct.monitors[1]
                if crop_rect and crop_rect.get("width", 0) > 200 and crop_rect.get("height", 0) > 200:
                    left = max(monitor["left"], crop_rect["left"])
                    top = max(monitor["top"], crop_rect["top"])
                    right = min(monitor["left"] + monitor["width"], crop_rect["left"] + crop_rect["width"])
                    bottom = min(monitor["top"] + monitor["height"], crop_rect["top"] + crop_rect["height"])
                    w = right - left
                    h = bottom - top
                    if w > 100 and h > 100:
                        sct_img = sct.grab({"left": left, "top": top, "width": w, "height": h})
                    else:
                        sct_img = sct.grab(monitor)
                else:
                    sct_img = sct.grab(monitor)

            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

            # Downscale if wider than max_width to control latency
            if img.width > max_width:
                scale = max_width / float(img.width)
                new_size = (max_width, int(img.height * scale))
                img = img.resize(new_size, Image.Resampling.BILINEAR)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            jpeg_bytes = buf.getvalue()
            b64_str = base64.b64encode(jpeg_bytes).decode("utf-8")
            return jpeg_bytes, b64_str
    except Exception as e:
        print(f"[ScreenCapture] Error capturing screen: {e}", flush=True)
        return None
