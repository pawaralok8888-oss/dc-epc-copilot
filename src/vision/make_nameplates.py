"""Generate synthetic nameplate photos from data/submittals.csv with Pillow.
Run from repo root: python src/vision/make_nameplates.py
Writes data/photos/*.png and data/photos/ground_truth.json
Planted error: EQ-BRK-05 photo shows 400 A (submittal and spec say 630 A).
Blurry example: second chiller photo, kept as a human-review case.
"""
import csv, json, random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "photos"
FD = "/usr/share/fonts/truetype/dejavu/"
MAKERS = {"AMPC": "Ampere Power", "VOLT": "VoltEdge", "GRID": "GridLine", "THER": "ThermaCore", "CHIL": "ChillFlow"}
# one clear photo per equipment, using its primary submittal
PRIMARY = ["SUB-001", "SUB-002", "SUB-004", "SUB-005", "SUB-006", "SUB-008", "SUB-009", "SUB-011", "SUB-012"]
WRONG = {"SUB-006": ("VOLT-BRK-400", 400)}   # photo value differs from submittal (630 A)
BLURRY = "SUB-008"                            # extra blurry chiller photo

def font(size, bold=False, mono=False):
    name = ("DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf") if mono else \
           ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    try:
        return ImageFont.truetype(FD + name, size)
    except OSError:
        return ImageFont.load_default()

def draw_plate(maker, model, rating, unit, tag, seed):
    rnd = random.Random(seed)
    W, H = 900, 600
    bg = Image.new("RGB", (W, H), (70 + rnd.randint(0, 20),) * 3)
    d = ImageDraw.Draw(bg)
    for _ in range(1500):
        g = rnd.randint(55, 100)
        d.point((rnd.randint(0, W), rnd.randint(0, H)), fill=(g, g, g))
    px, py, pw, ph = 100, 120, 700, 340
    d.rounded_rectangle((px + 6, py + 6, px + pw + 6, py + ph + 6), 18, fill=(40, 40, 40))
    d.rounded_rectangle((px, py, px + pw, py + ph), 18, fill=(205, 208, 210), outline=(120, 120, 125), width=5)
    for cx, cy in [(px + 25, py + 25), (px + pw - 25, py + 25), (px + 25, py + ph - 25), (px + pw - 25, py + ph - 25)]:
        d.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), fill=(150, 150, 155), outline=(90, 90, 90), width=2)
    d.text((px + 60, py + 28), maker.upper(), font=font(34, True), fill=(150, 20, 20))
    d.line((px + 60, py + 78, px + pw - 60, py + 78), fill=(100, 100, 100), width=2)
    y = py + 98
    for k, v in [("MODEL", model), ("RATING", f"{rating} {unit}"), ("TAG", tag)]:
        d.text((px + 60, y), k, font=font(22), fill=(80, 80, 85))
        d.text((px + 210, y - 6), v, font=font(34, True, mono=True), fill=(20, 20, 25))
        y += 56
    d.text((px + 60, y + 6), f"Serial {maker[:2].upper()}2026{rnd.randint(1000, 9999)}", font=font(19), fill=(60, 60, 65))
    return bg

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    subs = {r["submittal_id"]: r for r in csv.DictReader(open(ROOT / "data" / "submittals.csv"))}
    jobs = [(s, "ok") for s in PRIMARY] + [(BLURRY, "blurry")]
    truth = []
    for i, (sid, variant) in enumerate(jobs, 1):
        s = subs[sid]
        model, rating = s["model"], float(s["rating_value"])
        if sid in WRONG and variant == "ok":
            model, rating = WRONG[sid]; variant = "wrong"
        rating = int(rating) if rating == int(rating) else rating
        tag = s["equipment_id"].replace("EQ-", "")
        img = draw_plate(MAKERS[model.split("-")[0]], model, rating, s["unit"], tag, seed=i)
        if variant == "blurry":
            img = img.filter(ImageFilter.GaussianBlur(9)).resize((450, 300)).resize((900, 600))
        else:
            img = img.rotate(random.Random(i).uniform(-1.5, 1.5), resample=Image.BICUBIC, fillcolor=(80, 80, 80))
        pid = f"PH-{i:02d}"
        fname = f"{pid}_{tag.lower()}{'_blurry' if variant == 'blurry' else ''}.png"
        img.save(OUT / fname)
        truth.append(dict(id=pid, equipment_id=s["equipment_id"], submittal_id=sid, clause_id=s["clause_id"],
                          file=fname, model=model, rating_value=rating, unit=s["unit"], tag=tag, variant=variant,
                          submittal_rating=float(s["rating_value"]), mismatch=(variant == "wrong")))
    (OUT / "ground_truth.json").write_text(json.dumps(truth, indent=2))
    print(f"Wrote {len(truth)} images to {OUT}")

if __name__ == "__main__":
    main()
