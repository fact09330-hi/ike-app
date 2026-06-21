"""Ike App アイコン生成（エディトリアル・モノグラム）
PNG（各サイズ）と .icns を出力。スタンドアロン.appとロゴに使用。
使い方: python generate_icon.py
"""
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw

ASSETS = Path(__file__).parent / "assets"
INK = (20, 20, 20)
CREAM = (250, 251, 249)
COBALT = (40, 64, 230)
GRAY_BG = (231, 229, 224)


def rounded(draw, box, r, fill):
    draw.rounded_rectangle(box, radius=r, fill=fill)


def draw_icon(size=1024, bg=INK, mark=CREAM, accent=COBALT, pad_ratio=0.0):
    """4倍解像度で描いて縮小（アンチエイリアス）"""
    S = size * 4
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # タイル（角丸正方形）
    m = int(S * 0.06)
    rounded(d, [m, m, S - m, S - m], r=int(S * 0.20), fill=bg)

    # セリフ体の "I"
    cx = S // 2
    stem_w = int(S * 0.12)
    bar_w = int(S * 0.34)
    bar_h = int(S * 0.075)
    top = int(S * 0.30)
    bot = int(S * 0.70)
    # 上バー
    d.rectangle([cx - bar_w // 2, top, cx + bar_w // 2, top + bar_h], fill=mark)
    # 下バー
    d.rectangle([cx - bar_w // 2, bot - bar_h, cx + bar_w // 2, bot], fill=mark)
    # 縦棒
    d.rectangle([cx - stem_w // 2, top, cx + stem_w // 2, bot], fill=mark)

    # コバルトのアクセント（タイムライン的な水平バー）
    acc_w = int(S * 0.40)
    acc_h = int(S * 0.045)
    acc_y = int(S * 0.785)
    rounded(d, [cx - acc_w // 2, acc_y, cx + acc_w // 2, acc_y + acc_h],
            r=acc_h // 2, fill=accent)
    # アクセントの点（イベント/チェック）
    dot = int(S * 0.055)
    d.ellipse([cx + acc_w // 2 - dot, acc_y + acc_h // 2 - dot // 2 - dot // 2,
               cx + acc_w // 2 + dot, acc_y + acc_h // 2 + dot // 2 + dot // 2],
              fill=accent)

    return img.resize((size, size), Image.LANCZOS)


def main():
    ASSETS.mkdir(exist_ok=True)

    # メインPNG（ロゴ用・透明背景タイル）
    icon = draw_icon(512)
    icon.save(ASSETS / "ike_icon.png")
    icon.resize((256, 256), Image.LANCZOS).save(ASSETS / "ike_icon_256.png")
    icon.resize((64, 64), Image.LANCZOS).save(ASSETS / "ike_icon_64.png")
    print(f"✅ PNG: {ASSETS / 'ike_icon.png'}")

    # .icns 用 iconset（macOS標準サイズ）
    iconset = ASSETS / "IkeApp.iconset"
    iconset.mkdir(exist_ok=True)
    specs = [
        (16, "16x16"), (32, "16x16@2x"), (32, "32x32"), (64, "32x32@2x"),
        (128, "128x128"), (256, "128x128@2x"), (256, "256x256"),
        (512, "256x256@2x"), (512, "512x512"), (1024, "512x512@2x"),
    ]
    for px, name in specs:
        draw_icon(px).save(iconset / f"icon_{name}.png")

    # iconutil で .icns 生成（macOS）
    try:
        subprocess.run(["iconutil", "-c", "icns", str(iconset),
                        "-o", str(ASSETS / "IkeApp.icns")], check=True)
        print(f"✅ ICNS: {ASSETS / 'IkeApp.icns'}")
    except Exception as e:
        print(f"⚠️ icns生成スキップ（iconutil不可）: {e}")


if __name__ == "__main__":
    main()
