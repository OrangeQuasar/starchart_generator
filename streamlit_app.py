import sys
import tempfile
import types
from datetime import date, datetime
from pathlib import Path

import streamlit as st
from main import generate_chart, CITIES

_TIMEZONES = [
    "Asia/Tokyo", "Asia/Seoul", "Asia/Shanghai", "Asia/Singapore",
    "Asia/Kolkata", "Australia/Sydney",
    "Europe/London", "Europe/Paris", "Europe/Berlin",
    "America/New_York", "America/Chicago", "America/Los_Angeles",
    "America/Honolulu", "UTC",
]
_DIR_LABELS = ["（全天）", "北", "北東", "東", "南東", "南", "南西", "西", "北西"]
_DIR_VALUES = {
    "（全天）": "", "北": "北", "北東": "北東", "東": "東", "南東": "南東",
    "南": "南", "南西": "南西", "西": "西", "北西": "北西",
}


class _StdoutCapture:
    encoding = "utf-8"
    errors = "replace"

    def __init__(self, status_cb):
        self._cb = status_cb

    def write(self, text):
        t = text.strip()
        if t:
            self._cb(t)

    def flush(self): pass
    def reconfigure(self, **_): pass


def _run_generate(args, status_cb):
    old = sys.stdout
    sys.stdout = _StdoutCapture(status_cb)
    try:
        generate_chart(args)
    finally:
        sys.stdout = old


def main():
    st.set_page_config(
        page_title="星図つくれるサイト",
        page_icon="🌟",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    if "img_bytes" not in st.session_state:
        st.session_state.img_bytes = None
    if "img_ext" not in st.session_state:
        st.session_state.img_ext = ".png"

    # ── Sidebar ──────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.title("設定")

        st.subheader("観測地")
        city_names = ["（手動入力）"] + list(CITIES.keys())
        city = st.selectbox("都市", city_names, index=city_names.index("東京"))

        if city == "（手動入力）":
            lat = st.number_input("緯度", value=35.6762, format="%.4f",
                                   min_value=-90.0, max_value=90.0)
            lon = st.number_input("経度", value=139.6503, format="%.4f",
                                   min_value=-180.0, max_value=180.0)
            timezone = st.selectbox("タイムゾーン", _TIMEZONES)
            loc_name = st.text_input("地名（任意）", value="")
        else:
            lat, lon, timezone = CITIES[city]
            st.caption(f"緯度 {lat:.4f}°  経度 {lon:.4f}°  {timezone}")
            loc_name = city

        st.subheader("日時")
        use_now = st.checkbox("現在時刻を使用", value=True)
        if use_now:
            dt_str = ""
        else:
            d = st.date_input("日付", value=date.today())
            t = st.time_input("時刻",
                               value=datetime.now().time().replace(second=0, microsecond=0))
            dt_str = f"{d}T{t.strftime('%H:%M:%S')}"

        st.subheader("表示設定")
        lang = st.radio("言語", ["ja", "en"],
                         format_func=lambda x: "日本語" if x == "ja" else "English",
                         horizontal=True)
        direction = st.selectbox("方向", _DIR_LABELS)
        min_mag = st.slider("限界等級", min_value=1.0, max_value=7.0, value=5.5, step=0.5)

        c1, c2 = st.columns(2)
        with c1:
            show_mw  = st.checkbox("天の川",       value=True)
            show_cl  = st.checkbox("星座線",       value=True)
            show_cn  = st.checkbox("星座名",       value=True)
        with c2:
            show_sn  = st.checkbox("恒星名",       value=True)
            show_pn  = st.checkbox("惑星名",       value=True)
            show_ast = st.checkbox("季節の大図形",  value=True)

        st.subheader("出力設定")
        dpi = st.select_slider("DPI", options=[72, 96, 150, 200, 300], value=150)
        fmt = st.radio("形式", ["PNG", "JPG"], horizontal=True)

        st.divider()
        generate = st.button("星図を作成", type="primary", use_container_width=True)

    # ── Main area ─────────────────────────────────────────────────────────────────
    st.title("星図をつくります")

    if generate:
        ext = ".jpg" if fmt == "JPG" else ".png"
        args = types.SimpleNamespace(
            city="",
            lat=lat,
            lon=lon,
            elevation=0.0,
            location_name=loc_name,
            datetime=dt_str,
            timezone=timezone,
            lang=lang,
            direction=_DIR_VALUES.get(direction, ""),
            min_mag=min_mag,
            no_milky_way=not show_mw,
            no_constellation_lines=not show_cl,
            no_constellation_names=not show_cn,
            no_star_names=not show_sn,
            no_planet_names=not show_pn,
            no_asterisms=not show_ast,
            title="",
            dpi=dpi,
            force_refresh=False,
            output="",
        )

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            args.output = f.name

        status_box = st.empty()
        with st.spinner("星図を生成中... (初回はカタログのダウンロードに数十秒かかります)"):
            try:
                _run_generate(
                    args,
                    lambda msg: status_box.caption(msg),
                )
                with open(args.output, "rb") as f:
                    st.session_state.img_bytes = f.read()
                st.session_state.img_ext = ext
                status_box.empty()
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
                st.session_state.img_bytes = None
            finally:
                Path(args.output).unlink(missing_ok=True)

    if st.session_state.img_bytes:
        st.image(st.session_state.img_bytes, use_container_width=True)
        mime = "image/jpeg" if st.session_state.img_ext == ".jpg" else "image/png"
        st.download_button(
            "📥 ダウンロード",
            st.session_state.img_bytes,
            f"starchart{st.session_state.img_ext}",
            mime,
        )
    else:
        st.info("左のサイドバーで設定を調整し、「星図を作成」を押してください。")
        st.caption("初回実行時は星カタログのダウンロード（約10 MB）が発生します。")


if __name__ == "__main__":
    main()
