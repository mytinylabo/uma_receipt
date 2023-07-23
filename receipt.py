from tempfile import NamedTemporaryFile
import streamlit as st
from PIL import Image, ImageDraw

from modules.cv2_util import match_template, to_cv2

N_IMAGE_COLS = 3
THUMBNAIL_SIZE = (600, 600)

LOAD_TMP_FILE = "__load_image_"
SAVE_TMP_FILE = "__save_image_.png"

SESSION_STATE = {
    "loaded_ids": set(),
    "src_images": [],
    "merged_image": None,
}

# st.session_state が長いのでエイリアス
st_state = st.session_state

for k, v in SESSION_STATE.items():
    if k not in st_state:
        st_state[k] = v

with st.sidebar:
    # 画像アップロード
    uploaded_files = st.file_uploader("画像アップロード", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
    for file in sorted(uploaded_files, key=lambda f: f.name):
        if file.id not in st_state.loaded_ids:
            tmp_file = NamedTemporaryFile()
            with open(LOAD_TMP_FILE, "w+b") as f:
                f.write(file.getvalue())
            orig = Image.open(LOAD_TMP_FILE)
            thumb = orig.copy()
            thumb.thumbnail(THUMBNAIL_SIZE)
            st_state.src_images.append((orig, thumb))
            st_state.loaded_ids.add(file.id)

    # 縦結合動作設定
    cols_matching = st.columns(2)
    cols_matching[0].number_input("マッチング位置(%)", min_value=0, max_value=100, value=79, step=1, key="match_pos")
    cols_matching[1].number_input("マッチング幅(%)", min_value=1, max_value=20, value=5, step=1, key="match_height")

    st.write("---")
    st.write("**結合後切り取り**")
    st.checkbox("有効", value=True, key="crop_result")
    cols_crop_lt = st.columns(2)
    cols_crop_rb = st.columns(2)
    cols_crop_lt[0].number_input("左(px)", min_value=0, value=20, step=1, key="crop_left")
    cols_crop_lt[1].number_input("上(px)", min_value=0, value=312, step=1, key="crop_top")
    cols_crop_rb[0].number_input("右(px)", min_value=0, value=20, step=1, key="crop_right")
    cols_crop_rb[1].number_input("下(px)", min_value=0, value=520, step=1, key="crop_bottom")

    st.write("---")
    st.write("**スクロールバー消去**")
    st.checkbox("有効", value=True, key="remove_scrollbar")
    cols_remove_lt = st.columns(2)
    cols_remove_rb = st.columns(2)
    cols_remove_lt[0].number_input("左(px)", min_value=0, value=1231, step=1, key="remove_left")
    cols_remove_lt[1].number_input("上(px)", min_value=0, value=1323, step=1, key="remove_top")
    cols_remove_rb[0].number_input("右(px)", min_value=0, value=29, step=1, key="remove_right")
    cols_remove_rb[1].number_input("下(px)", min_value=0, value=567, step=1, key="remove_bottom")

    st.color_picker("塗り潰し色", value="#f2f2f2", key="remove_color")

_, _, col_delete_all = st.columns(3)
if col_delete_all.button("全削除", use_container_width=True):
    st_state.src_images = []
    st_state.merged_image = None
    st.experimental_rerun()

# サムネイル表示
image_cols = []
for i in range((len(st_state.src_images) // N_IMAGE_COLS) + 1):
    image_cols += st.columns(N_IMAGE_COLS)

all_same_size = True

for i, ((orig, thumb), col) in enumerate(zip([*st_state.src_images], image_cols)):
    # 画像のサイズが全て同じかどうかをチェック
    if i > 0:
        if orig.size != st_state.src_images[0][0].size:
            all_same_size = False

    disp_thumb = thumb.copy()
    # マッチング位置を赤線で表示
    if i < len(st_state.src_images) - 1:
        draw_thumb = ImageDraw.Draw(disp_thumb)
        match_pos_px = int(disp_thumb.height * (st_state.match_pos / 100))
        match_height_px = int(disp_thumb.height * (st_state.match_height / 100))
        box_rect = (0, match_pos_px - match_height_px, disp_thumb.width - 1, match_pos_px)
        draw_thumb.rectangle(box_rect, outline=(255, 0, 0))

    col.image(disp_thumb)

    # 操作ボタン
    col_left, col_delete, col_right = col.columns(3)
    if col_left.button("←", use_container_width=True, key=f"left_{i}", disabled=(i == 0)):
        st_state.src_images[i], st_state.src_images[i - 1] = st_state.src_images[i - 1], st_state.src_images[i]
        st_state.merged_image = None
        st.experimental_rerun()
    if col_delete.button("削除", use_container_width=True, key=f"delete_{i}"):
        del st_state.src_images[i]
        st_state.merged_image = None
        st.experimental_rerun()
    if col_right.button("→", use_container_width=True, key=f"right_{i}", disabled=(i == len(st_state.src_images) - 1)):
        st_state.src_images[i], st_state.src_images[i + 1] = st_state.src_images[i + 1], st_state.src_images[i]
        st_state.merged_image = None
        st.experimental_rerun()

if st.button("縦方向自動結合", use_container_width=True, disabled=((len(st_state.src_images) < 1) or not all_same_size)):
    # merged_image = st_state.src_images[0][0].copy()

    # マッチング位置を計算
    first_image, _ = st_state.src_images[0]
    match_pos_px = int(first_image.height * (st_state.match_pos / 100))
    match_height_px = int(first_image.height * (st_state.match_height / 100))
    crop_rect = (0, match_pos_px - match_height_px, first_image.width, match_pos_px)

    match_ys = []

    for i in range(len(st_state.src_images) - 1):
        # 順番に次画像との結合位置を計算
        image_up, _ = st_state.src_images[i]
        image_down, _ = st_state.src_images[i + 1]

        template = image_up.crop(crop_rect)
        if matched := match_template(to_cv2(image_down), to_cv2(template), 0.9, best=True):
            match_ys.append(matched[1])

    if len(match_ys) == len(st_state.src_images) - 1:
        if len(match_ys) == 0:
            # 一枚のみの場合
            st_state.merged_image = ("auto_vertical", first_image, False)
        else:
            # 結合後の画像の高さを計算
            merged_height = first_image.height
            for y in match_ys:
                merged_height += match_pos_px - match_height_px - y

            # 結合画像を作成
            merged_image = Image.new("RGB", (first_image.width, merged_height))
            merged_image.paste(first_image, (0, 0))
            offset_y = match_pos_px - match_height_px
            for (img, _), y in zip(st_state.src_images[1:], match_ys):
                cropped = img.crop((0, y, img.width, img.height))
                merged_image.paste(cropped, (0, offset_y))
                offset_y += match_pos_px - match_height_px - y

            st_state.merged_image = ("auto_vertical", merged_image, False)

    else:
        st.error("結合できませんでした。画像の順番を確認してください。")

if st.button("横方向単純結合", use_container_width=True, disabled=len(st_state.src_images) < 1):
    # 結合後の画像の幅を計算
    merged_width = sum([img.width for img, _ in st_state.src_images])
    # 結合後の画像の高さは最大のものに合わせる
    merged_height = max([img.height for img, _ in st_state.src_images])

    # 結合画像を作成
    merged_image = Image.new("RGB", (merged_width, merged_height), color="#fafafa")
    offset_x = 0
    for img, _ in st_state.src_images:
        merged_image.paste(img, (offset_x, 0))
        offset_x += img.width

    st_state.merged_image = ("simple_horizontal", merged_image, False)

if st_state.merged_image:
    merge_type, merged_image, edited = st_state.merged_image
    merged_image_display = merged_image.copy()

    if edited:
        # 加工済みなのでそのまま表示
        merged_image.save(SAVE_TMP_FILE, format="png")

    else:
        if merge_type == "auto_vertical":
            draw_guide = ImageDraw.Draw(merged_image_display)
            merged_image_save = merged_image.copy()
            draw_save = ImageDraw.Draw(merged_image_save)

            if st_state.remove_scrollbar:
                remove_rect = (st_state.remove_left,
                               st_state.remove_top,
                               merged_image_display.width - st_state.remove_right,
                               merged_image_display.height - st_state.remove_bottom)
                draw_guide.rectangle(remove_rect, outline=(0, 0, 255))
                # 保存用
                draw_save.rectangle(remove_rect, fill=st_state.remove_color)

            if st_state.crop_result:
                crop_rect = (st_state.crop_left,
                             st_state.crop_top,
                             merged_image_display.width - st_state.crop_right,
                             merged_image_display.height - st_state.crop_bottom)
                draw_guide.rectangle(crop_rect, outline=(255, 0, 0))
                # 保存用
                merged_image_save = merged_image_save.crop(crop_rect)

            merged_image_save.save(SAVE_TMP_FILE, format="png")

        elif merge_type == "simple_horizontal":
            # 単純横結合はそのまま表示
            merged_image.save(SAVE_TMP_FILE, format="png")

    st.write("\n\n")
    with open(SAVE_TMP_FILE, "rb") as file:
        st.download_button(label="画像をダウンロード",
                           data=file,
                           file_name="merged.png",
                           mime="image/png",
                           use_container_width=True)

    if merge_type == "auto_vertical" and not edited:
        if st.button("加工を適用", use_container_width=True):
            st_state.merged_image = (merge_type, merged_image_save, True)
            st.experimental_rerun()

    st.image(merged_image_display)
