#!/usr/bin/env python3
"""組織図の背景用の地図画像を、地理院タイル（標準）から切り出して作る。
出力: assets/nagai-map-bg.png と assets/nagai-map-bg.json（bbox・寸法・ズーム）。
座標の対応は Web メルカトルで計算し、build.py が同じ bbox で位置を割り出す。
出典: 国土地理院 地理院タイル https://maps.gsi.go.jp/development/ichiran.html
"""
import json, math, urllib.request
from io import BytesIO
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
Z = 13
BBOX = {"min_lat": 38.045, "max_lat": 38.155, "min_lng": 139.945, "max_lng": 140.095}
URL = "https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png"

def px(lat, lng, z):
    n = 2 ** z
    x = (lng + 180.0) / 360.0 * n * 256
    lat_r = math.radians(lat)
    y = (1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi) / 2.0 * n * 256
    return x, y

def main():
    x0, y0 = px(BBOX["max_lat"], BBOX["min_lng"], Z)  # 左上
    x1, y1 = px(BBOX["min_lat"], BBOX["max_lng"], Z)  # 右下
    tx0, ty0 = int(x0 // 256), int(y0 // 256)
    tx1, ty1 = int(x1 // 256), int(y1 // 256)
    cols, rows = tx1 - tx0 + 1, ty1 - ty0 + 1
    canvas = Image.new("RGB", (cols * 256, rows * 256), (240, 240, 240))
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            url = URL.format(z=Z, x=tx, y=ty)
            req = urllib.request.Request(url, headers={"User-Agent": "sengoku-guide-prototype"})
            with urllib.request.urlopen(req, timeout=30) as r:
                tile = Image.open(BytesIO(r.read())).convert("RGB")
            canvas.paste(tile, ((tx - tx0) * 256, (ty - ty0) * 256))
    left, top = int(x0 - tx0 * 256), int(y0 - ty0 * 256)
    right, bottom = int(x1 - tx0 * 256), int(y1 - ty0 * 256)
    img = canvas.crop((left, top, right, bottom))
    out = ROOT / "assets" / "nagai-map-bg.png"
    img.save(out)
    meta = {**BBOX, "zoom": Z, "width": img.width, "height": img.height,
            "source": "地理院タイル（標準）", "source_url": "https://maps.gsi.go.jp/development/ichiran.html"}
    (ROOT / "assets" / "nagai-map-bg.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK {out} {img.width}x{img.height} tiles={cols}x{rows}")

if __name__ == "__main__":
    main()
