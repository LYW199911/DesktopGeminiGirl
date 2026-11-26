import random
from typing import Dict, Optional, Tuple
import numpy as np


def _find_salient_patch(win_rect: Dict[str, int], sw: int, sh: int) -> Optional[Tuple[int, int]]:
    """
    Captures a fast thumbnail of win_rect and picks one of the highest-detail
    (text/code/image) sub-regions so the pet lands near real content, not blank margins.
    """
    try:
        import mss
        from PIL import Image

        wl = int(win_rect["left"])
        wt = int(win_rect["top"])
        ww = int(win_rect["width"])
        wh = int(win_rect["height"])
        if ww < sw or wh < sh:
            return None

        with mss.mss() as sct:
            raw = sct.grab({"left": wl, "top": wt, "width": ww, "height": wh})
            im = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

        # Downsample to ~320px wide for <15ms saliency scoring
        scale = min(1.0, 320.0 / max(1, ww))
        tw = max(32, int(round(ww * scale)))
        th = max(32, int(round(wh * scale)))
        gray = np.asarray(im.resize((tw, th), Image.Resampling.BILINEAR).convert("L"), dtype=np.float32)

        # Edge / text / detail energy
        gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
        gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
        energy = gx + gy

        pw = max(8, int(round(sw * scale)))
        ph = max(8, int(round(sh * scale)))
        step_x = max(4, (tw - pw) // 4) if tw > pw else 1
        step_y = max(4, (th - ph) // 3) if th > ph else 1

        candidates = []
        for py in range(0, max(1, th - ph + 1), step_y):
            for px in range(0, max(1, tw - pw + 1), step_x):
                patch_e = float(energy[py:py + ph, px:px + pw].mean())
                candidates.append((patch_e, int(wl + px / scale), int(wt + py / scale)))

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        top_k = candidates[:min(3, len(candidates))]
        _, best_sx, best_sy = random.choice(top_k)
        return best_sx, best_sy
    except Exception:
        return None


def pick_focus_target(
    win_rect: Optional[Dict[str, int]],
    screen_left: int,
    screen_top: int,
    screen_w: int,
    screen_h: int,
    pet_w: int,
    pet_h: int,
    current_y: Optional[int] = None,
    prefer_bottom_walk: bool = False,
) -> Tuple[int, int, Dict[str, int]]:
    """
    Computes a purposeful (target_x, target_y) and a localized content-rich sub-region
    dict {'left', 'top', 'width', 'height'} to inspect & critique.
    Enforces pure horizontal translation (ty == current_y) unless |dy| >= 140px.
    """
    margin = 12
    min_x = screen_left + margin
    max_x = max(min_x, screen_left + screen_w - pet_w - margin)
    min_y = screen_top + margin
    max_y = max(min_y, screen_top + screen_h - pet_h - 5)
    base_y = max_y if current_y is None else max(min_y, min(max_y, int(current_y)))

    if not win_rect or win_rect.get("width", 0) < 260 or win_rect.get("height", 0) < 200:
        win_rect = {
            "left": screen_left + int(screen_w * 0.1),
            "top": screen_top + int(screen_h * 0.1),
            "width": int(screen_w * 0.8),
            "height": int(screen_h * 0.8),
        }

    wl = max(screen_left, int(win_rect["left"]))
    wt = max(screen_top, int(win_rect["top"]))
    wr = min(screen_left + screen_w, int(win_rect["left"]) + int(win_rect["width"]))
    wb = min(screen_top + screen_h, int(win_rect["top"]) + int(win_rect["height"]))
    ww = max(260, wr - wl)
    wh = max(200, wb - wt)

    # Focused small block (~40% of window, good for a sentence block or small image)
    sw = max(320, min(560, int(ww * 0.40)))
    sh = max(220, min(380, int(wh * 0.40)))
    sw = min(sw, ww)
    sh = min(sh, wh)

    salient = _find_salient_patch({"left": wl, "top": wt, "width": ww, "height": wh}, sw, sh)
    if salient:
        sx, sy = salient
    else:
        sx = wl + random.randint(0, max(0, ww - sw))
        sy = wt + random.randint(0, max(0, wh - sh))

    # Perch right beside the focused sub-region
    tx = sx + sw - int(pet_w * 0.25)
    if tx > max_x:
        tx = sx - int(pet_w * 0.75)
    tx = max(min_x, min(max_x, tx))

    if prefer_bottom_walk:
        # Pure horizontal walk along current baseline (no Y change!)
        ty = base_y
    else:
        raw_ty = max(min_y, min(max_y, sy + sh - int(pet_h * 0.85)))
        # Only use Y-axis flight if height change is genuinely large (>= 140px);
        # otherwise keep Y unchanged so she just walks horizontally!
        if abs(raw_ty - base_y) < 140:
            ty = base_y
        else:
            ty = raw_ty

    sub_rect = {"left": int(sx), "top": int(sy), "width": int(sw), "height": int(sh)}
    return int(tx), int(ty), sub_rect
