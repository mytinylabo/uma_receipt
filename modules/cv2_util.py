import numpy as np
import cv2


def to_cv2(pil_image):
    """PIL 画像を OpenCV 形式の画像に変換する。
    """
    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)


def match_template(image, template, threathold, best=False):
    """画像のマッチングを行う。
       （image の中から template のパターンを探す）
    """
    ih, iw = image.shape[:2]
    th, tw = template.shape[:2]

    # テンプレート画像は小さいこと
    assert ih >= th and iw >= tw

    # マッチング
    all_matches = cv2.matchTemplate(
        image, template, cv2.TM_CCOEFF_NORMED)

    # 一致度が閾値以上のマッチ箇所をリストで取得
    results = [(x, y, all_matches[y, x])
               for x, y in zip(*np.where(all_matches >= threathold)[::-1])]

    if best:
        # スコアが最も高い結果だけ返す（閾値を超えた結果がなければ None）
        # (x, y, score)
        return max(results, key=lambda x: x[-1]) if results else None

    # 複数結果を返すケースでは重複を削除する
    # 検出範囲が被っているうち、最もスコアが高いものを残す
    def test(r):
        ax, ay, a_score = r
        acx = ax + tw // 2
        acy = ay + th // 2
        for bx, by, b_score in results:
            if (bx < acx < bx + tw) and (by < acy < by + th):
                # 検出位置が被る結果のうち
                if a_score < b_score:
                    # よりスコアが高いものがある場合テスト失敗
                    return False
        return True

    # [(x, y, score), (x, y, score), ...]
    return list(filter(test, results))


def match_templates(image, templates, threathold):
    """複数テンプレートでマッチングする。
       同じ領域に複数のテンプレートがマッチした場合、一致度の高いものを結果にする。

       数字やアイコンなど、同じような大きさのものが画像中に並んでいるときに
       それら種類を識別する用途を想定しているため、テンプレート画像の大きさが
       バラバラだとおかしな結果になるかも。いやなる。
    """
    # テンプレート 1 個ずつマッチングを行って結果をリストにまとめていく
    detected = []
    for i, template in enumerate(templates):
        results = match_template(image, template, threathold)
        detected.extend(map(lambda r: (r[0], r[1], r[2], i), results))

    # 検出範囲が被っているうち、最もスコアが高いものを残す。
    # 例えば image 中のある個所の 8 という画像パターンに対して
    # templates 中の 3 も 8 も threathold を超えて検出とみなされているとき、
    # スコアを比べて 8 だけを残す。
    def test(r):
        ax, ay, a_score, ai = r
        ah, aw = templates[ai].shape[:2]
        acx = ax + aw // 2
        acy = ay + ah // 2
        for bx, by, b_score, bi in detected:
            bh, bw = templates[bi].shape[:2]
            if (bx < acx < bx + bw) and (by < acy < by + bh):
                # 検出位置が被る結果のうち
                if a_score < b_score:
                    # よりスコアが高いものがある場合テスト失敗
                    return False
        return True

    # [(x, y, score, index), (x, y, score, index), ...]
    # index は templates 中のどれがマッチしたかを示す
    return list(filter(test, detected))


def compare_images(image_a, image_b):
    """二つの画像の一致度を調べる。
       （image_b のサイズは image_a 以下である必要がある）
    """
    detected = match_template(image_a, image_b, 0.0, best=True)
    return detected[2] if detected else 0.0
