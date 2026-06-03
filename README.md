# 星図生成プログラム (seizu)

指定した場所・日時の全天または特定方向の星図を PNG 画像として出力します。  
**GUI**（`uv run gui.py`）と **CLI**（`uv run main.py`）の両方で操作できます。

---

## 必要環境

| 項目 | バージョン |
|------|-----------|
| Python | 3.11 以上 |
| [uv](https://docs.astral.sh/uv/) | 最新版推奨 |

依存ライブラリ（uv が自動インストール）: `astropy`, `matplotlib`, `numpy`, `tzdata`

---

## セットアップ

```bash
git clone <repo-url>
cd seizu
uv run main.py          # 初回実行時に依存パッケージを自動インストール
```

初回はカタログデータ（恒星・星座線）をネットからダウンロードして  
`~/.seizu/` にキャッシュします（数秒かかります）。

---

## 起動方法

### GUI モード（推奨）

```bash
uv run gui.py           # GUI を直接起動
uv run main.py --gui    # main.py 経由で GUI を起動
```

設定パネル（左）で各種オプションを選択し、「★ 星図を生成」ボタンを押すと  
右のプレビューエリアに結果が表示されます。追加の依存ライブラリは不要です（tkinter 標準搭載）。

### CLI モード

```bash
uv run main.py [オプション]
```

---

## クイックスタート（CLI）

```bash
# 東京・現在時刻の全天星図（デフォルト）
uv run main.py

# 都市名を指定して保存先を変更
uv run main.py --city 大阪 --output osaka.png

# 日時を指定
uv run main.py --city 東京 --datetime "2025-08-01T22:00:00"

# 特定の方向の半円星図（南方向）
uv run main.py --direction 南 --output south.png
```

---

## オプション一覧

### 観測地 / Location

| オプション | 既定値 | 説明 |
|-----------|--------|------|
| `--city CITY` | *(なし)* | 都市名プリセット（→ [対応都市一覧](#対応都市一覧)）。`--lat` / `--lon` / `--timezone` を自動設定し、タイトルに都市名を表示 |
| `--lat DEG` | `35.6762` | 緯度（北緯を正で指定） |
| `--lon DEG` | `139.6503` | 経度（東経を正で指定） |
| `--elevation M` | `0` | 標高（メートル） |
| `--location-name NAME` | *(なし)* | タイトルに表示する地名。未指定時は座標を表示 |

### 日時 / Date & Time

| オプション | 既定値 | 説明 |
|-----------|--------|------|
| `--datetime YYYY-MM-DDTHH:MM:SS` | *(現在時刻)* | 観測日時（現地時刻で指定） |
| `--timezone TZ` | `Asia/Tokyo` | タイムゾーン（IANA 名、例: `America/New_York`） |

### 表示 / Display

| オプション | 説明 |
|-----------|------|
| `--lang ja\|en` | ラベル言語。`ja`（日本語、既定）または `en`（英語） |
| `--min-mag MAG` | 表示限界等級（既定 `5.5`）。小さくすると明るい星のみ、大きくすると暗い星まで表示 |
| `--direction DIR` | 半円星図モード（→ [方向指定モード](#方向指定モード)） |
| `--no-milky-way` | 天の川を非表示 |
| `--no-constellation-lines` | 星座線を非表示 |
| `--no-constellation-names` | 星座名を非表示 |
| `--no-star-names` | 恒星名を非表示（デフォルトは 1 等星以上に表示） |
| `--no-planet-names` | 惑星名を非表示 |
| `--no-asterisms` | 季節の大図形を非表示 |

### 出力 / Output

| オプション | 既定値 | 説明 |
|-----------|--------|------|
| `--output FILE` | `starchart.png` | 出力ファイル名（PNG） |
| `--title TEXT` | *(自動生成)* | タイトル文字列を上書き |
| `--dpi N` | `150` | 解像度。`300` にすると印刷用の高解像度画像を生成 |
| `--force-refresh` | *(なし)* | カタログを再ダウンロード（データが古い場合や破損時に使用） |

---

## 方向指定モード

`--direction` オプションで特定方向の半円星図を生成します。  
指定した方向が中央下（地平線上）に配置され、天頂が上端になります。

```bash
uv run main.py --direction 南    # 東〜南〜西を表示
uv run main.py --direction 北    # 西〜北〜東を表示
uv run main.py --direction 東    # 北〜東〜南を表示
uv run main.py --direction 南西   # 南〜南西〜西を表示
```

指定できる方向:

| 日本語 | 英語 | 方位角 |
|--------|------|--------|
| 北 | N | 0° |
| 北東 | NE | 45° |
| 東 | E | 90° |
| 南東 | SE | 135° |
| 南 | S | 180° |
| 南西 | SW | 225° |
| 西 | W | 270° |
| 北西 | NW | 315° |

---

## 表示内容

### 星

- **HYG データベース v4.1**（約 8,900 星、6.5 等まで）を使用
- 表示限界等級は `--min-mag` で調整可能（既定 5.5 等）
- **恒星名**: 1 等星以上（約 20 星）のみ表示。日本語モードではカタカナ名（シリウス、ベテルギウス等）を使用

### 天の川

銀河面に沿ったランダムサンプリング（17,000 点）を 2D 密度マップに変換し、  
ガウシアンぼかしをかけて自然な輝きを再現します。`--no-milky-way` で非表示。

### 惑星

月・水星・金星・火星・木星・土星を表示（天王星・海王星は除く）。  
月は大きな円形マーカー、その他はひし形マーカーで描画。

### 星座線・星座名

**Stellarium** のモダン星座データを使用（88 星座）。  
星座線は明るい青色（見やすさ重視）で描画します。

### 季節の大図形

| 名称 | 構成星 | 線の色 |
|------|--------|--------|
| 春の大曲線 | アリオト・ミザール・アルカイド・アークトゥルス・スピカ | 緑 |
| 夏の大三角 | ベガ・デネブ・アルタイル | 青 |
| 秋の大四辺形 | マルカブ・シェアト・アルフェラッツ・アルゲニブ | オレンジ |
| 冬の大三角 | シリウス・ベテルギウス・プロキオン | 赤橙 |
| 冬の大六角形 | シリウス・リゲル・アルデバラン・カペラ・ポルックス・プロキオン | 金 |

`--no-asterisms` で非表示。

### 方位・高度

- 8 方位ラベル（北 / 北東 / 東 / 南東 / 南 / 南西 / 西 / 北西）
- 高度 30°・60° の参考線（破線）
- 天頂マーカー（`+`）

---

## 対応都市一覧

### 日本国内

| 都市名（日本語） | 都市名（英語） |
|----------------|--------------|
| 東京 | Tokyo |
| 横浜 | Yokohama |
| 名古屋 | Nagoya |
| 大阪 | Osaka |
| 京都 | Kyoto |
| 神戸 | Kobe |
| 広島 | Hiroshima |
| 福岡 | Fukuoka |
| 仙台 | Sendai |
| 札幌 | Sapporo |
| 那覇 | Naha |

いずれも日本語・英語どちらでも指定可能です。例: `--city 大阪` と `--city Osaka` は同じです。

### 海外

`New York` / `Los Angeles` / `Chicago` / `Honolulu` /  
`London` / `Paris` / `Berlin` / `Sydney` / `Beijing` / `Seoul` / `Singapore`

スペースを含む都市名はクォートで囲んでください: `--city "New York"`

---

## 使用例

```bash
# 夏の天の川（東京・2025年8月）
uv run main.py --city 東京 --datetime "2025-08-01T22:00:00" --output summer.png

# 冬の大三角・大六角形（大阪・1月）
uv run main.py --city 大阪 --datetime "2025-01-15T21:00:00" --output winter.png

# 南方向の半円星図（高解像度・印刷用）
uv run main.py --direction 南 --dpi 300 --output south_hires.png

# 英語ラベルでニューヨーク
uv run main.py --city "New York" --lang en --output ny.png

# 惑星・星座のみ（星名・天の川・大図形は非表示）
uv run main.py --no-star-names --no-milky-way --no-asterisms --output minimal.png

# 任意の場所を緯度経度で指定
uv run main.py --lat 43.06 --lon 141.35 --location-name 札幌 --timezone Asia/Tokyo

# カタログデータを最新に更新して生成
uv run main.py --force-refresh
```

---

## キャッシュについて

初回起動時に `~/.seizu/` へ以下のデータをダウンロード・保存します。

| ファイル | 内容 | ソース |
|---------|------|--------|
| `hyg.pkl` | HYG 恒星カタログ（約 8,900 星） | astronexus/HYG-Database |
| `constellations.pkl` | 星座線データ（88 星座） | Stellarium skycultures |

データが古くなった場合は `--force-refresh` で再取得できます。

---

## データ出典

- **恒星カタログ**: [HYG Database v4.1](https://github.com/astronexus/HYG-Database) (MIT License)
- **星座線**: [Stellarium](https://github.com/Stellarium/stellarium) modern skyculture (GPL)
- **天文計算**: [Astropy](https://www.astropy.org/) (BSD License)
