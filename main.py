import time
import cv2

from src.capture.screen import capture_screen
from src.coords.base import GOLD_POS, LEVEL_POS, ROUND_POS
from src.vision.crop import crop_center
from src.vision.ocr import (
    read_gold_safe,
    read_round_safe,
    read_level_ultra,
    gold_debug_threshold,
    level_debug_threshold,
)

# ====== TUNING ======
SLEEP = 0.15
HUD_MISSING_FRAMES = 3
MAX_GOLD = 300
MAX_LEVEL = 12

ROUND_W, ROUND_H = 180, 40
GOLD_W, GOLD_H = 60, 40
LEVEL_W, LEVEL_H = 50, 50

ZOOM_ROUND = 6
ZOOM_GOLD = 10
ZOOM_LEVEL = 8
ZOOM_THR = 2

LEVEL_CONFIRM = 4

# GOLD anti-sintilação:
GOLD_CONFIRM = 2          # precisa repetir 2 frames pra aceitar
GOLD_HOLD_FRAMES = 8      # se falhar OCR, segura último gold por ~8 frames (8*0.15=1.2s)
GOLD_MAX_JUMP = 40        # ignora saltos > 40 em 0.15s (leitura louca)
# ====================

last = {"round": None, "gold": None, "level": None}
missing_counter = 0
hud_hidden = False

# anti-oscilação level
level_candidate = None
level_count = 0

# anti-oscilação gold
gold_candidate = None
gold_count = 0
gold_hold = 0


def to_int_safe(s):
    try:
        return int(s)
    except:
        return None


def show_zoom(win_name, img, scale=6):
    zoom = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    cv2.imshow(win_name, zoom)


# janelas
cv2.namedWindow("ROUND_CROP (LIVE)", cv2.WINDOW_NORMAL)
cv2.namedWindow("GOLD_CROP (LIVE)", cv2.WINDOW_NORMAL)
cv2.namedWindow("LEVEL_CROP (LIVE)", cv2.WINDOW_NORMAL)
cv2.namedWindow("GOLD_THRESH (LIVE)", cv2.WINDOW_NORMAL)
cv2.namedWindow("LEVEL_THRESH (LIVE)", cv2.WINDOW_NORMAL)
cv2.namedWindow("LEVEL_THRESH_INV (LIVE)", cv2.WINDOW_NORMAL)

cv2.moveWindow("ROUND_CROP (LIVE)", 30, 30)
cv2.moveWindow("GOLD_CROP (LIVE)", 30, 260)
cv2.moveWindow("LEVEL_CROP (LIVE)", 30, 520)
cv2.moveWindow("GOLD_THRESH (LIVE)", 450, 260)
cv2.moveWindow("LEVEL_THRESH (LIVE)", 450, 520)
cv2.moveWindow("LEVEL_THRESH_INV (LIVE)", 780, 520)

print("Rodando... (ESC para sair)")

while True:
    img = capture_screen()

    round_crop = crop_center(img, ROUND_POS, ROUND_W, ROUND_H)
    gold_crop = crop_center(img, GOLD_POS, GOLD_W, GOLD_H)
    level_crop = crop_center(img, LEVEL_POS, LEVEL_W, LEVEL_H)

    show_zoom("ROUND_CROP (LIVE)", round_crop, scale=ZOOM_ROUND)
    show_zoom("GOLD_CROP (LIVE)", gold_crop, scale=ZOOM_GOLD)
    show_zoom("LEVEL_CROP (LIVE)", level_crop, scale=ZOOM_LEVEL)

    show_zoom("GOLD_THRESH (LIVE)", gold_debug_threshold(gold_crop), scale=ZOOM_THR)
    show_zoom("LEVEL_THRESH (LIVE)", level_debug_threshold(level_crop, invert=False), scale=ZOOM_THR)
    show_zoom("LEVEL_THRESH_INV (LIVE)", level_debug_threshold(level_crop, invert=True), scale=ZOOM_THR)

    rnd = read_round_safe(round_crop)
    gold_str = read_gold_safe(gold_crop, max_gold=MAX_GOLD)
    lvl_str = read_level_ultra(level_crop, max_level=MAX_LEVEL)

    # ROUND
    if rnd != "" and rnd != last["round"]:
        print(f"ROUND mudou: {last['round']} -> {rnd}")
        last["round"] = rnd

    gold = to_int_safe(gold_str) if gold_str != "" else None
    lvl = to_int_safe(lvl_str) if lvl_str != "" else None

    gold_ok = (gold is not None) and (0 <= gold <= MAX_GOLD)
    lvl_ok = (lvl is not None) and (1 <= lvl <= MAX_LEVEL)

    # HUD oculto
    if (not gold_ok) and (not lvl_ok):
        missing_counter += 1
    else:
        missing_counter = 0

    if missing_counter >= HUD_MISSING_FRAMES and not hud_hidden:
        hud_hidden = True
        print("HUD oculto (adversário/carrossel) -> mantendo últimos valores")
    elif missing_counter == 0 and hud_hidden:
        hud_hidden = False
        print("HUD voltou -> retomando leitura")

    if not hud_hidden:
        # ===== GOLD anti-sintilação =====
        if gold_ok:
            # anti-salto
            if last["gold"] is not None and abs(gold - last["gold"]) > GOLD_MAX_JUMP:
                pass
            else:
                # confirma por repetição
                if gold_candidate == gold:
                    gold_count += 1
                else:
                    gold_candidate = gold
                    gold_count = 1

                if gold_count >= GOLD_CONFIRM:
                    if last["gold"] != gold:
                        print(f"GOLD mudou: {last['gold']} -> {gold}")
                        last["gold"] = gold
                    gold_hold = 0
        else:
            # se falhou OCR, segura o último valor por um tempo
            if last["gold"] is not None and gold_hold < GOLD_HOLD_FRAMES:
                gold_hold += 1
            # não printa nada, só não deixa piscar

        # ===== LEVEL (anti-oscilação) =====
        if lvl_ok:
            if level_candidate == lvl:
                level_count += 1
            else:
                level_candidate = lvl
                level_count = 1

            if level_count >= LEVEL_CONFIRM and last["level"] != lvl:
                print(f"LEVEL mudou: {last['level']} -> {lvl}")
                last["level"] = lvl

    if cv2.waitKey(1) & 0xFF == 27:
        break

    time.sleep(SLEEP)

cv2.destroyAllWindows()
print("Saiu.")
