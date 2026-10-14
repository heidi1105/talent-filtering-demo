"""
00_seed_must_include.py — build the must-include anchor list.

Writes seed/must_include.json: the anchor list of Korean talents that the seed
MUST contain. 03_reconcile_load.py
grades the harvested seed against this file and refuses to load (without
--force) if any are missing.

Run:  python 00_seed_must_include.py
No network, no DB.
"""
import json
from pathlib import Path

SEED = Path(__file__).resolve().parent / "seed"
SEED.mkdir(exist_ok=True)

# (name_en, name_native_or_blank, group_or_blank)
IDOLS = [
    ("Jang Won-young", "장원영", "IVE"), ("An Yu-jin", "안유진", "IVE"),
    ("Mingyu", "김민규", "SEVENTEEN"), ("S.Coups", "최승철", "SEVENTEEN"),
    ("Joshua", "조슈아", "SEVENTEEN"), ("Yeji", "황예지", "ITZY"),
    ("Taeyang", "태양", "BIGBANG"), ("Johnny", "쟈니", "NCT"),
    ("Ten", "텐", "WayV"), ("Seulgi", "슬기", "Red Velvet"),
    ("Yeri", "예리", "Red Velvet"), ("Irene", "아이린", "Red Velvet"),
    ("Joy", "조이", "Red Velvet"), ("Wendy", "웬디", "Red Velvet"),
    ("Miyeon", "미연", "(G)I-DLE"), ("Yuri", "권유리", "Girls' Generation"),
    ("Sooyoung", "최수영", "Girls' Generation"), ("Hyoyeon", "효연", "Girls' Generation"),
    ("Taeyeon", "태연", "Girls' Generation"), ("Son Na-eun", "손나은", "Apink"),
    ("Jung Eun-ji", "정은지", "Apink"), ("Baekhyun", "백현", "EXO"),
    ("Suho", "수호", "EXO"), ("Karina", "카리나", "aespa"),
    ("Song Mino", "송민호", "WINNER"), ("B.I", "비아이", "iKON"),
    ("Ok Taec-yeon", "옥택연", "2PM"), ("Krystal", "크리스탈", "f(x)"),
    ("Hyeri", "혜리", "Girl's Day"), ("Jacob", "제이콥", "The Boyz"),
    ("Juyeon", "주연", "The Boyz"), ("Kim Se-jeong", "김세정", "Gugudan"),
    ("Rain", "비", ""), ("Lee Hi", "이하이", ""),
    ("Sandara Park", "산다라박", "2NE1"), ("Gray", "그레이", ""),
    ("LOREN", "로렌", ""),
]
GROUPS = [("STAYC", "스테이씨"), ("Treasure", "트레저")]
ACTORS = [
    ("Lee Soo-hyuk", "이수혁"), ("Park So-dam", "박소담"), ("Kwon Nara", "권나라"),
    ("Lee Da-hee", "이다희"), ("Kim Hye-yoon", "김혜윤"), ("Cho Yi-hyun", "조이현"),
    ("Cha Ju-young", "차주영"), ("Lee Yu-bi", "이유비"), ("Han Ji-hyun", "한지현"),
    ("Na In-woo", "나인우"), ("Seol In-ah", "설인아"), ("Park Bo-young", "박보영"),
    ("Kim You-jung", "김유정"), ("Park Ji-hu", "박지후"), ("Kim Tae-ri", "김태리"),
    ("Lim Ji-yeon", "임지연"), ("Go Min-si", "고민시"), ("Shin Hye-sun", "신혜선"),
    ("Go Youn-jung", "고윤정"), ("Jung So-min", "정소민"), ("Park Gyu-young", "박규영"),
    ("Lee Jae-wook", "이재욱"), ("Ji Chang-wook", "지창욱"), ("Nam Joo-hyuk", "남주혁"),
    ("Song Joong-ki", "송중기"), ("Park Seo-jun", "박서준"), ("Lee Dong-wook", "이동욱"),
    ("Lee Sung-kyoung", "이성경"), ("Kim Da-mi", "김다미"),
]

def build():
    out = []
    for n, k, g in IDOLS:
        out.append({"name_en": n, "name_native": k or None, "type": "idol", "group": g or None})
    for n, k in GROUPS:
        out.append({"name_en": n, "name_native": k or None, "type": "group", "group": None})
    for n, k in ACTORS:
        out.append({"name_en": n, "name_native": k or None, "type": "actor", "group": None})
    return out

def main():
    data = build()
    (SEED / "must_include.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(data)} anchors -> seed/must_include.json")

if __name__ == "__main__":
    main()
