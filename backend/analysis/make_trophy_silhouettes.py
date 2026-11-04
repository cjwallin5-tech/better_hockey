"""One-off: build a solid silhouette of every NHL trophy for the site's trophy icons.

Downloads each trophy's photo from the NHL records site (the photos are shot on a black background), turns it into a white shape on a
transparent background and writes frontend/public/trophies/<trophy id>.png. The site draws these as CSS masks, so one file takes the
text colour in both themes. Run it again if the NHL adds a trophy:

    python backend/analysis/make_trophy_silhouettes.py [output dir]

Needs Pillow and numpy.

Two ways to find the shape in a photo, and which one looks right depends on the trophy:
- "outline" (the default): threshold the photo, close small gaps, fill enclosed holes and smooth the edge. Keeps real outlines, so
  figures, flames and crowns survive.
- "rows": also fills every row between the object's left and right edge. Trophies that are cups on a base are close to symmetric, so
  this closes their dark reflective sides and gives a clean cup shape; it ruins anything with fine structure.
A few awards are not shot as a cup on black (clear glass slabs, a winner posing beside the trophy, a grey backdrop), so those are
listed in SPECIAL and drawn or tuned individually. Some are traced by hand: "polygons"  are points read off the photo on a grid
(x, y in the grid picture, which is the photo cropped at `origin` and enlarged `scale` times), drawn on top of whatever the photo
gives; "mask_from" and "mask_until" throw away the detected shape above or below those photo rows so traced parts can replace ragged ones.
"""
import io
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

FEED = "https://records.nhl.com/site/api/trophy"
HEIGHT = 240          # px; icons show at 20-130px so this is generous
USER_AGENT = {"User-Agent": "Mozilla/5.0"}

OUTLINE = {"cutoff": 10, "blur": 2, "close": 15, "smooth": 3.5, "fill_holes": True}   # brightest channel above `cutoff` counts as trophy
ROWS = {"cutoff": 20, "close": 9, "fill_rows": True}

# Generic shapes (left half, x from the centre line, y from the top, on a 100 x 150 canvas), mirrored to make the full outline.
CUP_HALF = [(50, 6), (20, 6), (22, 22), (30, 40), (43, 54), (46, 64), (46, 100), (38, 108), (30, 110), (28, 120), (16, 120), (16, 136), (50, 136)]
SLAB = [(18, 30), (82, 8), (82, 126), (18, 148)]  # a tall glass award with a slanted top

# Hand-traced parts. Each polygon is [(x, y), ...] in the grid picture used to read it off: the photo cropped at `origin`, drawn `scale`x.
MESSIER_FIGURE = [(468, 72), (490, 60), (512, 68), (522, 95), (548, 105), (580, 100), (600, 108), (620, 140), (632, 180), (620, 232), (612, 262),
                  (642, 292), (702, 326), (746, 332), (742, 346), (714, 382), (690, 394), (662, 388), (642, 420), (640, 476), (470, 476),
                  (404, 468), (410, 424), (422, 372), (430, 300), (416, 244), (404, 216), (386, 186), (380, 160), (400, 142), (442, 128),
                  (466, 120), (470, 98)]
MESSIER_BASE = [(290, 458), (660, 486), (736, 402), (792, 406), (800, 440), (812, 470), (822, 500), (876, 520), (890, 575), (900, 620),
                (890, 650), (948, 688), (940, 696), (772, 914), (500, 888), (200, 850), (62, 836), (76, 814), (150, 810), (152, 632),
                (208, 620), (214, 590), (206, 502), (250, 490)]
GM_BOWL = [(292, 100), (300, 78), (420, 62), (540, 58), (660, 62), (765, 85), (772, 100), (760, 150), (745, 200), (715, 250), (675, 305),
           (625, 335), (540, 350), (470, 335), (410, 300), (360, 250), (335, 195), (318, 140)]
GM_STATUES = [(330, 372), (375, 366), (408, 384), (425, 420), (470, 440), (498, 400), (500, 300), (498, 250), (512, 180), (552, 178), (550, 260),
              (575, 310), (605, 330), (640, 345), (655, 385), (690, 388), (722, 384), (752, 392), (758, 440), (775, 470), (790, 540),
              (792, 620), (765, 680), (745, 730), (765, 790), (800, 846), (775, 856), (750, 850), (640, 848), (430, 848), (305, 848),
              (298, 790), (305, 720), (285, 620), (300, 560), (318, 470)]
GM_PLATFORM = [(295, 850), (775, 850), (775, 880), (530, 892), (295, 880)]
RICHARD_BASE = [(462, 640), (860, 640), (860, 656), (830, 690), (850, 780), (868, 880), (910, 1000), (920, 1075), (935, 1110), (905, 1130),
                (820, 1140), (500, 1140), (445, 1135), (405, 1105), (422, 1060), (430, 990), (450, 880), (470, 780), (490, 695), (462, 660)]
GM_BASE = [  # Jim Gregory GM award: the plinth, its ledge and the wooden base under the statues
    [(220, 895), (875, 895), (875, 1340), (220, 1340)],
    [(205, 1338), (892, 1338), (892, 1415), (205, 1415)],
    [(160, 1415), (935, 1415), (938, 1650), (158, 1650)],
]

SPECIAL = {
    **{i: {"method": "rows"} for i in (1, 3, 4, 5, 6, 8, 9, 11, 16)},                   # cups on bases: Stanley Cup, Lady Byng, Calder, ...
    14: {"method": "outline", "cutoff": 18, "blur": 1, "close": 5, "smooth": 2, "fill_holes": False},  # Presidents' Trophy: keep the gaps between its rods
    20: {"shape": "cup"},                                       # Lifetime Achievement: the photo has the winner standing next to it
    21: {"shape": "slab"},                                      # Foundation Player Award: clear glass
    24: {"shape": "slab"},                                      # E.J. McGuire Award of Excellence: clear glass
    25: {"method": "rows", "cutoff": 90, "fill_rows": False},   # Willie O'Ree: grey backdrop, and the open ribbons should stay open
    15: {"method": "outline", "cutoff": 90, "blur": 1, "close": 3, "smooth": 2, "mask_until": 640,
         "origin": (2, 120), "scale": 2, "polygons": [RICHARD_BASE]},   # Rocket Richard: overexposed, so a high cutoff keeps the V of its panels apart from the player; traced base
    22: {"method": "trace", "origin": (34, 228), "scale": 2, "polygons": [MESSIER_FIGURE, MESSIER_BASE]},  # Messier: a glass figure, too faint to detect
    23: {"method": "trace", "origin": (39, 35), "scale": 2,
         "polygons": [GM_BOWL, GM_STATUES, GM_PLATFORM, *GM_BASE]},         # GM of the Year: bowl, three statues and base, all traced
}


def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url.strip(), headers=USER_AGENT), timeout=60).read()


def _pad(img, pad=4):
    framed = Image.new("L", (img.width + 2 * pad, img.height + 2 * pad), 0)
    framed.paste(img, (pad, pad))
    return framed


def _fill_outside_in(mask):
    """Fill every hole: flood the outside from the border; whatever the flood did not reach is inside the shape."""
    padded = _pad(mask)
    ImageDraw.floodfill(padded, (0, 0), 128)
    return padded.point(lambda v: 0 if v == 128 else 255).crop((4, 4, padded.width - 4, padded.height - 4))


def _fill_rows(mask):
    """Fill each row between the object's left and right edge (see the module note)."""
    a = np.asarray(mask) > 127
    out = np.zeros_like(a)
    for y in range(a.shape[0]):
        xs = np.flatnonzero(a[y])
        if xs.size >= 3:
            out[y, xs[0]:xs[-1] + 1] = True
    return Image.fromarray((out * 255).astype("uint8"))


def _brightest(photo):
    return Image.fromarray(np.asarray(Image.open(io.BytesIO(photo)).convert("RGB")).max(axis=2).astype("uint8"))


def outline_mask(photo, cutoff, blur, close, smooth, fill_holes):
    mask = _brightest(photo).filter(ImageFilter.GaussianBlur(blur)).point(lambda v: 255 if v > cutoff else 0)
    if close > 1:
        mask = mask.filter(ImageFilter.MaxFilter(close)).filter(ImageFilter.MinFilter(close))
    if fill_holes:
        mask = _fill_outside_in(mask)
    return mask.filter(ImageFilter.GaussianBlur(smooth)).point(lambda v: 255 if v > 127 else 0)  # blur + threshold rounds off the edge


def rows_mask(photo, cutoff, close, fill_rows):
    mask = _brightest(photo).point(lambda v: 255 if v > cutoff else 0)
    mask = mask.filter(ImageFilter.MedianFilter(5))                                         # specks of JPEG noise
    mask = mask.filter(ImageFilter.MaxFilter(close)).filter(ImageFilter.MinFilter(close))  # close small gaps
    filled = _fill_outside_in(mask)
    if fill_rows:
        filled = filled.filter(ImageFilter.MinFilter(9)).filter(ImageFilter.MaxFilter(9))  # drop thin spurs before the rows are filled across them
        filled = _fill_rows(filled).filter(ImageFilter.MedianFilter(7))                    # the median smooths the stair-steps
    return filled


def traced(polygons, origin, scale, size):
    """The hand-traced polygons drawn at photo size (grid-picture points are converted back to photo pixels)."""
    img = Image.new("L", size, 0)
    draw = ImageDraw.Draw(img)
    for pts in polygons:
        draw.polygon([(origin[0] + x / scale, origin[1] + y / scale) for x, y in pts], fill=255)
    return img


def shape_mask(kind):
    """A generic outline: a cup, or a slanted glass slab."""
    scale = 4
    img = Image.new("L", (100 * scale, 150 * scale), 0)
    pts = CUP_HALF + [(100 - x, y) for x, y in reversed(CUP_HALF)] if kind == "cup" else SLAB
    ImageDraw.Draw(img).polygon([(x * scale, y * scale) for x, y in pts], fill=255)
    return img


def make_mask(photo, special):
    if "shape" in special:
        return shape_mask(special["shape"])
    tracing = {k: special[k] for k in ("origin", "scale", "polygons") if k in special}
    size = Image.open(io.BytesIO(photo)).size
    if special.get("method") == "trace":
        return traced(tracing["polygons"], tracing["origin"], tracing["scale"], size)
    options = {k: v for k, v in special.items() if k not in ("method", "mask_from", "mask_until", *tracing)}
    mask = rows_mask(photo, **{**ROWS, **options}) if special.get("method") == "rows" else outline_mask(photo, **{**OUTLINE, **options})
    if "mask_until" in special:
        mask.paste(0, (0, special["mask_until"], mask.width, mask.height))  # drop the detected shape below this row
    if "mask_from" in special:
        mask.paste(0, (0, 0, mask.width, special["mask_from"]))              # ... and above this one
    if tracing:
        mask = ImageChops.lighter(mask, traced(tracing["polygons"], tracing["origin"], tracing["scale"], size))
    return mask


def to_icon(mask):
    """White-on-transparent RGBA image of the mask, cropped to the object and scaled to HEIGHT."""
    box = mask.getbbox()
    if box is None:
        raise ValueError("nothing found in the photo")
    mask = mask.crop(box)
    scale = HEIGHT / mask.height
    soft = mask.filter(ImageFilter.GaussianBlur(1.0)).resize((max(1, round(mask.width * scale)), HEIGHT), Image.LANCZOS)
    out = Image.new("RGBA", soft.size, (255, 255, 255, 0))
    out.putalpha(soft)
    return out


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "frontend" / "public" / "trophies"
    out_dir.mkdir(parents=True, exist_ok=True)
    for t in json.loads(fetch(FEED))["data"]:
        url = (t.get("imageUrl") or "").strip()
        special = SPECIAL.get(t["id"], {})
        try:
            photo = fetch(url) if url and "shape" not in special else None
            img = to_icon(make_mask(photo, special) if photo or "shape" in special else shape_mask("cup"))  # no photo at all: a generic cup
        except Exception as e:  # one bad photo should not stop the rest
            print(f"{t['id']:>3} {t['name']}: failed ({e})")
            continue
        img.save(out_dir / f"{t['id']}.png", optimize=True)
        print(f"{t['id']:>3} {t['name']}: {img.width}x{img.height}")


if __name__ == "__main__":
    main()
