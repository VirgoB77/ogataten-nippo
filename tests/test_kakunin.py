"""取得可否確認（preflight。common/kado.py の kakunin）の検査（2026-09-27・統括判断）。

**本物の相手には1本も出さない。** 通信は偽の相手（test_kado の Nise）が受ける。
許可の出どころは、一時フォルダに作った git の置き場で確かめる。予約台帳は一時フォルダの bare repo。

見ること：
    許可が無い・形が違う・運営者の手でない・期限の外・使用済み → **通信0で止まる**
    出すのは robots.txt・一覧・詳細の最大3本。GET だけ。見出しは名乗りだけ。転送は辿らない
    拒否・認証・CAPTCHA・想定外の転送 → 残りを出さずに止まる
    記録は上書きしない。**本文を残さない**
    許可は本番の承認にならない（本番の門は今までどおり止まる）

    python3 -m unittest discover -s tests
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

try:
    import test_kado as tk                      # unittest discover -s tests のとき
except ImportError:                             # python3 -m unittest tests.test_kakunin のとき
    from tests import test_kado as tk

kado = tk.kado
HOST, REPO, UA = tk.HOST, tk.REPO, tk.UA
SID = "tameshi-ken"
KID = "tameshi-ken-2026-09-25-1"
ROBOTS = "https://%s/robots.txt" % HOST
ICHIRAN = "https://%s/auction/list" % HOST
SHOUSAI = "https://%s/auction/item/123" % HOST
# 本文の目印。**記録にも、置き場のどこにも残ってはいけない**
MEJIRUSHI = b"HONBUN-NO-MEJIRUSHI-9f3a"
ICHIRAN_OK = (200, {"Content-Type": "text/html; charset=utf-8"},
              "<html><body>".encode() + MEJIRUSHI + "現在価格 入札数 <a href=\"/auction/item/123\">x</a>"
              "<a href=\"https://www.example.com/auction/item/9\">よそ</a></body></html>".encode("utf-8"))
SHOUSAI_OK = (200, {"Content-Type": "text/html"},
              "<html>".encode() + MEJIRUSHI + "現在価格 入札数 入札履歴</html>".encode("utf-8"))


class Nise(tk.Nise):
    """偽の相手。要求の方法（GET 等）と見出しも控える。"""

    def __init__(self, kotae):
        super().__init__(kotae)
        self.hoho, self.midashi = [], []

    def _open(self, req):
        self.hoho.append(req.get_method())
        self.midashi.append({k.lower(): v for k, v in req.header_items()})
        return super()._open(req)

    https_open = _open
    http_open = _open


def yomu(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def yoi_kyoka(**kae):
    k = {"approval_id": KID, "source_id": SID, "purpose": "acquisition_preflight",
         "issued_by": "operator", "issued_at": "2026-09-25T06:00:00+09:00",
         "expires_at": "2026-09-26T06:00:00+09:00", "allowed_kinds": ["robots", "list", "detail"],
         "max_requests": 3, "min_interval_seconds": 5, "single_use": True}
    k.update(kae)
    return k


def yoi_pf_card(**kae):
    c = {"source_id": SID, "カード版": 1, "目的": "取得してよいかを判断する材料を取る",
         "URL": {"list": ICHIRAN, "detail_pattern": r"https://www\.example\.lg\.jp/auction/item/[0-9]+"},
         "確かめる項目": {"現在価格": ["現在価格"], "入札数": ["入札数"], "入札履歴": ["入札履歴"]}}
    c.update(kae)
    return c


class PfOki(tk.Oki):
    """一時フォルダに、確認用カード・相手台帳・許可を置く。本番のカード（tameshi）は承認なしのまま。"""

    def setUp(self):
        super().setUp()
        self.daicho = {"yoyaku": {"hitsuyou": False},
                       "aite": {"ためし県": {"host": [HOST], "担当": "未定", "id": SID,
                                          "preflight": {"置き場": REPO, "実行": "PC参謀", "許可": "運営者"}}}}
        self.pf_cards = {SID: yoi_pf_card()}
        self.kaku_all()
        tk.git(self.root, "add", "-A")
        tk.git(self.root, "commit", "-q", "-m", "確認用のカードと相手台帳")

    def kaku_all(self):
        super().kaku_all()
        if hasattr(self, "pf_cards"):
            os.makedirs(self.p("data", "ref", "preflight"), exist_ok=True)
            self.kaku("data/ref/preflight/cards.json", {"cards": self.pf_cards})

    def kyoka(self, kid=KID, ai=False, bot=False, hozon=True, card=None, **kae):
        card = card or self.pf_cards[SID]
        k = yoi_kyoka(approval_id=kid, card_version=card["カード版"],
                      card_fingerprint=kado.card_shimon(card))
        k.update(kae)
        os.makedirs(self.p("data", "ref", "preflight", "approvals"), exist_ok=True)
        self.kaku("data/ref/preflight/approvals/%s.json" % kid, k)
        if not hozon:
            return
        tk.git(self.root, "add", "-A")
        msg = "取得可否確認の許可"
        if ai:
            msg += "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
        env = {"GIT_AUTHOR_NAME": "github-actions[bot]"} if bot else None
        tk.git(self.root, "commit", "-q", "-m", msg, env=env)

    def mon(self, kotae=None, **kw):
        self.nise = Nise(kotae if kotae is not None else {
            ROBOTS: tk.ROBOTS_OK, ICHIRAN: ICHIRAN_OK, SHOUSAI: SHOUSAI_OK})
        self.naps = []
        return kado.Kado(self.root, REPO, UA, env=self.env, transport=self.nise,
                         run_id=kw.pop("run_id", "run-1"), sleep=self.naps.append,
                         now=kw.pop("now", lambda: tk.ASA + 1000.0), **kw)

    def kiroku(self):
        d = self.p("data", "ref", "preflight", "records", SID)
        return [yomu(os.path.join(d, n)) for n in sorted(os.listdir(d))] if os.path.isdir(d) else []

    def tomaru(self, rec, kotoba):
        self.assertEqual(rec["result"], "STOP")
        self.assertIn(kotoba, rec["stop_reason"])


class 通るとき(PfOki):

    def test_robots・一覧・詳細の3本だけを_GETで_名乗りだけ付けて出す(self):
        self.kyoka()
        rec = self.mon().kakunin(KID)
        self.assertEqual(rec["result"], "完了", rec["stop_reason"])
        self.assertEqual(self.nise.kita, [ROBOTS, ICHIRAN, SHOUSAI])
        self.assertEqual(self.nise.hoho, ["GET"] * 3)
        for m in self.nise.midashi:
            # 付けるのは名乗りだけ（Host は urllib が付ける）。Cookie・Authorization を付けない
            self.assertLessEqual(set(m), {"user-agent", "host"})
        self.assertEqual(rec["external_requests"], 3)
        self.assertEqual(rec["detail_url_found"], True)

    def test_記録に観測の事実と判定が分かれて残る(self):
        self.kyoka()
        self.mon().kakunin(KID)
        (r,) = self.kiroku()
        for k in ("source_id", "approval_id", "run", "started_at", "finished_at", "external_requests",
                  "result", "stop_reason", "robots", "pages", "card_fingerprint"):
            self.assertIn(k, r)
        rb = r["robots"]
        self.assertEqual((rb["requested_url"], rb["final_url"], rb["http_status"], rb["redirect"]),
                         (ROBOTS, ROBOTS, 200, False))
        self.assertEqual((rb["response_kind"], rb["kujiraya_judgment"]), ("valid_robots", "通す"))
        self.assertEqual(len(rb["body_sha256"]), 64)
        p = r["pages"][0]
        for k in ("kind", "requested_url", "final_url", "http_status", "content_type", "redirect",
                  "auth_required", "captcha", "items", "stop_reason", "body_sha256"):
            self.assertIn(k, p)
        self.assertEqual(p["items"], {"現在価格": True, "入札数": True, "入札履歴": False})
        self.assertEqual(r["pages"][1]["items"]["入札履歴"], True)
        self.assertEqual(r["run"]["run_id"], "run-1")

    def test_本文は記録にも置き場のどこにも残らない(self):
        self.kyoka()
        self.mon().kakunin(KID)
        for d, _, fs in os.walk(self.root):
            if os.sep + ".git" in d + os.sep:
                continue
            for n in fs:
                with open(os.path.join(d, n), "rb") as f:
                    self.assertNotIn(MEJIRUSHI, f.read(), os.path.join(d, n))
        for d, _, fs in os.walk(self.kinko):
            self.assertEqual(fs, [], "金庫に何か書いた")

    def test_間隔は許可の秒数と5秒の長いほう(self):
        self.kyoka(min_interval_seconds=7)
        self.mon().kakunin(KID)
        self.assertEqual(self.naps, [7, 7])

    def test_詳細の型に合うリンクが無ければ_詳細は出さずに終わる(self):
        self.kyoka()
        kotae = {ROBOTS: tk.ROBOTS_OK,
                 ICHIRAN: (200, {"Content-Type": "text/html"}, "<html>現在価格</html>".encode("utf-8"))}
        rec = self.mon(kotae).kakunin(KID)
        self.assertEqual(rec["result"], "完了")
        self.assertEqual(rec["detail_url_found"], False)
        self.assertEqual(self.nise.kita, [ROBOTS, ICHIRAN])

    def test_robotsが拒否する詳細のリンクは選ばない(self):
        self.kyoka()
        kotae = {ROBOTS: (200, {"Content-Type": "text/plain"}, b"User-agent: *\nDisallow: /auction/item/\n"),
                 ICHIRAN: ICHIRAN_OK, SHOUSAI: SHOUSAI_OK}
        rec = self.mon(kotae).kakunin(KID)
        self.assertEqual(self.nise.kita, [ROBOTS, ICHIRAN])
        self.assertEqual(rec["detail_url_found"], False)

    def test_robotsが無い_404_は今の本番と同じく通す_ただし事実はnot_foundと残す(self):
        self.kyoka()
        kotae = {ROBOTS: (404, {}, b""), ICHIRAN: ICHIRAN_OK, SHOUSAI: SHOUSAI_OK}
        rec = self.mon(kotae).kakunin(KID)
        self.assertEqual(rec["robots"]["response_kind"], "not_found")
        self.assertEqual(rec["robots"]["kujiraya_judgment"], "通す")

    def test_パスワード欄があっても_確かめる語があれば止めない(self):
        self.kyoka()
        kotae = {ROBOTS: tk.ROBOTS_OK, SHOUSAI: SHOUSAI_OK,
                 ICHIRAN: (200, {"Content-Type": "text/html"},
                           '<html><input type="password">現在価格<a href="/auction/item/123">x</a></html>'
                           .encode("utf-8"))}
        rec = self.mon(kotae).kakunin(KID)
        self.assertEqual(rec["result"], "完了", rec["stop_reason"])


class 通信の前に止まる(PfOki):
    """どれも **偽の相手に1本も届かない**（nise.kita が空）。記録は残す。"""

    def tomete(self, kotoba, kid=KID, **kw):
        rec = self.mon(**kw).kakunin(kid)
        self.tomaru(rec, kotoba)
        self.assertEqual(self.nise.kita, [])
        self.assertEqual(rec["external_requests"], 0)
        return rec

    def test_許可が無い(self):
        self.tomete("許可が無い")

    def test_許可IDの形が違う(self):
        self.tomete("許可ID の形が違う", kid="../shounin/tameshi")

    def test_AIの印が付いた許可(self):
        self.kyoka(ai=True)
        self.tomete("AI の commit")

    def test_自動実行が入れた許可(self):
        self.kyoka(bot=True)
        self.tomete("自動実行の commit")

    def test_保存していない許可(self):
        self.kyoka(hozon=False)
        self.tomete("保存（commit）されていない")

    def test_保存したあとで書き換えた許可(self):
        self.kyoka()
        with open(self.p("data/ref/preflight/approvals/%s.json" % KID), "a", encoding="utf-8") as f:
            f.write(" ")
        self.tomete("書き換えられている")

    def test_許可の欄が決まりどおりでない(self):
        for kae, kotoba in (({"purpose": "production"}, "purpose"),
                            ({"issued_by": "pc-sanbo"}, "issued_by"),
                            ({"single_use": False}, "single_use"),
                            ({"allowed_kinds": ["list", "detail"]}, "robots が無い"),
                            ({"allowed_kinds": ["robots", "api"]}, "allowed_kinds"),
                            ({"max_requests": 4}, "max_requests"),
                            ({"max_requests": True}, "max_requests"),
                            ({"min_interval_seconds": 3}, "min_interval_seconds"),
                            ({"approval_id": "betsu"}, "ファイル名と違う"),
                            ({"expires_at": "2026-09-26T06:00:01+09:00"}, "24時間の内でない"),
                            ({"issued_at": "2026-09-25T06:00:00"}, "時差つき")):
            with self.subTest(kae=kae):
                self.setUp()
                self.kyoka(**kae)
                self.tomete(kotoba)

    def test_期限を過ぎた_発行の前(self):
        self.kyoka()
        self.tomete("期限", now=lambda: tk.jikoku("2026-09-26", "06:00:00"))
        self.setUp()
        self.kyoka(issued_at="2026-09-25T08:00:00+09:00", expires_at="2026-09-26T08:00:00+09:00")
        self.tomete("発行の前")

    def test_許可のあとでカードを変えた(self):
        self.kyoka()
        self.pf_cards[SID]["URL"]["list"] = "https://%s/auction/list?all=1" % HOST
        self.kaku_all()
        self.tomete("カード指紋")

    def test_相手台帳で_この置き場が確認の置き場でない(self):
        self.daicho["aite"]["ためし県"]["preflight"]["置き場"] = "betsu-repo"
        self.kaku_all()
        self.kyoka()
        self.tomete("取得可否確認をする置き場")

    def test_URLのhostが相手台帳に無い_https_でない_hostが2つ(self):
        for url, kotoba in (("https://www.example.com/auction/list", "相手台帳のその相手に無い"),
                            ("http://%s/auction/list" % HOST, "https でない"),
                            ("https://u:p@%s/auction/list" % HOST, "認証の情報")):
            with self.subTest(url=url):
                self.setUp()
                self.pf_cards[SID]["URL"]["list"] = url
                self.kaku_all()
                self.kyoka()
                self.tomete(kotoba)
        self.setUp()
        self.pf_cards[SID]["URL"] = {"list": ICHIRAN, "detail": "https://www.example.com/x"}
        self.kaku_all()
        self.kyoka()
        self.tomete("host が違う")

    def test_今日もう見た相手(self):
        self.kaku("data/ref/aite-kyou.json", {"ためし県": {"hi": "2026-09-25", "run": "run-0", "repo": "x"}})
        self.kyoka()
        self.tomete("今日もう見た")

    def test_この実行の中で本番が見た相手も止まる(self):
        # 本番のあとに重ねると、予約台帳の予約を使い回して、許可IDの跡が残らない
        self.kaku("data/ref/aite-kyou.json", {"ためし県": {"hi": "2026-09-25", "run": "run-1", "repo": REPO}})
        self.kyoka()
        self.tomete("今日もう見た")

    def test_同じ相手の本番カードに機械札(self):
        self.kaku("data/ref/kikai-fuda.json", {"tameshi": {"札": "停止要請", "理由": "相手から"}})
        self.kyoka()
        self.tomete("機械札")

    def test_本番の取得の最中には入らない(self):
        k = self.mon()
        k._genzai = ("tameshi", {}, ("自動取得",))
        self.kyoka()
        rec = k.kakunin(KID)
        self.tomaru(rec, "重ねない")
        self.assertEqual(self.nise.kita, [])

    def test_読めない記録があれば_使った側に倒す(self):
        d = self.p("data", "ref", "preflight", "records", SID)
        os.makedirs(d)
        with open(os.path.join(d, "kowareta.json"), "w", encoding="utf-8") as f:
            f.write("{")
        self.kyoka()
        self.tomete("読めない")


class 守りを1つずつ(PfOki):
    """同じ守りが入口（pf_mon）と1本ごとの関所（_pf_dasu）の両方にある。**片方ずつ確かめる**
    （両方を通しで試すだけだと、片方が壊れても、もう片方が止めて黙る）。"""

    def hiraku(self):
        self.kyoka()
        k = self.mon()
        ctx, riyuu = k.pf_mon(KID)
        self.assertEqual(riyuu, [])
        return k, ctx

    def test_入口は期限切れを理由に挙げる(self):
        self.kyoka()
        _, riyuu = self.mon(now=lambda: tk.jikoku("2026-09-26", "06:00:00")).pf_mon(KID)
        self.assertIn("許可の期限（expires_at）を過ぎた", riyuu)

    def test_関所は許可に無い種類を出さない(self):
        k, ctx = self.hiraku()
        ctx["kinds"] = ["robots"]
        with self.assertRaises(kado.Tomeru):
            k._pf_dasu(ctx, "list", ICHIRAN, 100)
        self.assertEqual(self.nise.kita, [])

    def test_関所は許された_hostの外へ出さない(self):
        k, ctx = self.hiraku()
        with self.assertRaises(kado.Tomeru):
            k._pf_dasu(ctx, "robots", "https://www.example.com/robots.txt", 100)
        self.assertEqual(self.nise.kita, [])

    def test_関所は期限を過ぎたら出さない(self):
        k, ctx = self.hiraku()
        ctx["kigen"] = tk.ASA
        with self.assertRaises(kado.Tomeru):
            k._pf_dasu(ctx, "robots", ROBOTS, 100)
        self.assertEqual(self.nise.kita, [])
        # 期限切れの許可で、その日の枠（今日の控え・予約台帳）を使わない（待つ段に入る前に止める）
        self.assertFalse(os.path.exists(self.p("data/ref/aite-kyou.json")))


class 一回限り(PfOki):

    def test_同じ許可の2回目は_通信0で止まる(self):
        self.kyoka()
        self.assertEqual(self.mon().kakunin(KID)["result"], "完了")
        rec = self.mon(run_id="run-2").kakunin(KID)
        self.tomaru(rec, "もう使われた")
        self.assertEqual(self.nise.kita, [])

    def test_同じ実行の中の2回目も止まる(self):
        self.kyoka()
        k = self.mon()
        k.kakunin(KID)
        n = len(self.nise.kita)
        rec = k.kakunin(KID)
        self.tomaru(rec, "もう使われた")
        self.assertEqual(len(self.nise.kita), n)

    def test_通信の前に止まった許可は_使ったことにならない(self):
        self.kaku("data/ref/aite-kyou.json", {"ためし県": {"hi": "2026-09-25", "run": "run-0", "repo": "x"}})
        self.kyoka()
        self.tomaru(self.mon().kakunin(KID), "今日もう見た")
        os.remove(self.p("data/ref/aite-kyou.json"))
        self.assertEqual(self.mon(run_id="run-2").kakunin(KID)["result"], "完了")

    def test_記録は上書きしない(self):
        self.kyoka()
        self.mon().kakunin(KID)
        self.mon().kakunin(KID)                                 # 同じ実行・同じ時刻（止まる）
        self.assertEqual(len(self.kiroku()), 2)


class 途中で止まる(PfOki):
    """止まったら**残りを出さない**。記録には何が返ったかを残す。"""

    def dasu(self, kotae):
        self.kyoka()
        return self.mon(kotae).kakunin(KID)

    def test_robotsが拒否(self):
        rec = self.dasu({ROBOTS: (200, {"Content-Type": "text/plain"}, b"User-agent: *\nDisallow: /\n"),
                         ICHIRAN: ICHIRAN_OK})
        self.tomaru(rec, "拒否")
        self.assertEqual(self.nise.kita, [ROBOTS])
        self.assertEqual(rec["robots"]["target_allowed"], {"list": False})

    def test_robotsが200でも中身がHTMLなら止まる(self):
        rec = self.dasu({ROBOTS: (200, {"Content-Type": "text/html"}, b"<!doctype html><html>top</html>"),
                         ICHIRAN: ICHIRAN_OK})
        self.tomaru(rec, "確かめられなかった")
        self.assertEqual(self.nise.kita, [ROBOTS])
        rb = rec["robots"]
        self.assertEqual((rb["http_status"], rb["response_kind"], rb["kujiraya_judgment"]),
                         (200, "html_response", "確かめられなかった"))

    def test_robotsの転送は辿らない(self):
        rec = self.dasu({ROBOTS: (301, {"Location": "https://%s/" % HOST}, b""), ICHIRAN: ICHIRAN_OK})
        self.tomaru(rec, "転送")
        self.assertEqual(self.nise.kita, [ROBOTS])
        self.assertEqual((rec["robots"]["response_kind"], rec["robots"]["redirect_to"]),
                         ("redirect", "https://%s/" % HOST))

    def test_robotsが混んでいる(self):
        rec = self.dasu({ROBOTS: (503, {}, b""), ICHIRAN: ICHIRAN_OK})
        self.tomaru(rec, "混んでいる")
        self.assertEqual(rec["robots"]["response_kind"], "unavailable")
        self.assertEqual(self.nise.kita, [ROBOTS])

    def test_一覧が断る_認証を求める(self):
        for st in (401, 403):
            with self.subTest(st=st):
                self.setUp()
                rec = self.dasu({ROBOTS: tk.ROBOTS_OK, ICHIRAN: (st, {}, b"no")})
                self.tomaru(rec, "断られた")
                self.assertEqual(self.nise.kita, [ROBOTS, ICHIRAN])
                self.assertTrue(rec["pages"][0]["auth_required"])
                kyou = yomu(self.p("data/ref/aite-kyou.json"))
                self.assertIn(str(st), kyou["ためし県"]["tomatta"])

    def test_一覧がログインへ転送する(self):
        rec = self.dasu({ROBOTS: tk.ROBOTS_OK,
                         ICHIRAN: (302, {"Location": "https://%s/login?next=/auction/list" % HOST}, b"")})
        self.tomaru(rec, "転送")
        self.assertEqual(self.nise.kita, [ROBOTS, ICHIRAN])
        self.assertIn("/login", rec["pages"][0]["redirect_to"])

    def test_相手の側で行き先が変わった(self):
        rec = self.dasu({ROBOTS: tk.ROBOTS_OK,
                         ICHIRAN: (200, {"Content-Type": "text/html"}, b"<html>x</html>",
                                   "https://%s/other" % HOST)})
        self.tomaru(rec, "転送")

    def test_一覧が混んでいる(self):
        rec = self.dasu({ROBOTS: tk.ROBOTS_OK, ICHIRAN: (429, {"Retry-After": "60"}, b"")})
        self.tomaru(rec, "混んでいる")
        self.assertEqual(self.nise.kita, [ROBOTS, ICHIRAN])

    def test_CAPTCHAの兆候(self):
        for kotae in ((200, {"Content-Type": "text/html"}, b'<div class="g-recaptcha"></div>'),
                      (403, {"cf-mitigated": "challenge"}, b"<html>checking</html>"),
                      (200, {"Content-Type": "text/html"}, b'<script src="https://challenges.cloudflare.com/turnstile/v0/api.js"></script>')):
            with self.subTest(kotae=kotae[:2]):
                self.setUp()
                rec = self.dasu({ROBOTS: tk.ROBOTS_OK, ICHIRAN: kotae, SHOUSAI: SHOUSAI_OK})
                self.assertEqual(rec["result"], "STOP")
                self.assertTrue(rec["pages"][0]["captcha"])
                self.assertEqual(self.nise.kita, [ROBOTS, ICHIRAN])

    def test_ログイン画面が200で返った(self):
        rec = self.dasu({ROBOTS: tk.ROBOTS_OK,
                         ICHIRAN: (200, {"Content-Type": "text/html"},
                                   b'<form><input name="pw" type="password"></form>'),
                         SHOUSAI: SHOUSAI_OK})
        self.tomaru(rec, "ログインを求める")
        self.assertEqual(self.nise.kita, [ROBOTS, ICHIRAN])

    def test_許可に無い種類は出さない(self):
        self.kyoka(allowed_kinds=["robots", "list"], max_requests=2)
        rec = self.mon().kakunin(KID)
        self.assertEqual(rec["result"], "完了")
        self.assertEqual(self.nise.kita, [ROBOTS, ICHIRAN])

    def test_本数を使い切ったら出さない(self):
        self.kyoka(max_requests=2)
        rec = self.mon().kakunin(KID)
        self.tomaru(rec, "使い切った")
        self.assertEqual(self.nise.kita, [ROBOTS, ICHIRAN])

    def test_待つ間に期限を過ぎたら出さない(self):
        tokei = [tk.jikoku("2026-09-26", "05:59:58")]

        def ima():
            return tokei[0]

        self.env["RUN_DATE"] = "2026-09-26"
        self.kyoka()
        k = self.mon(now=ima)
        k._sleep = lambda s: tokei.__setitem__(0, tokei[0] + s)
        rec = k.kakunin(KID)
        self.tomaru(rec, "期限")
        self.assertLessEqual(len(self.nise.kita), 1)


class 本番の承認にならない(PfOki):

    def test_確認のあとも_本番の門は今までどおり止まる(self):
        self.kyoka()
        k = self.mon()
        self.assertEqual(k.kakunin(KID)["result"], "完了")
        self.assertEqual(k.seishiki("tameshi"), "規約未確定")
        self.assertTrue(k.card_mon("tameshi", hozon_saki=os.path.join(self.kinko, "raw")))
        self.assertEqual(os.listdir(self.p("data", "ref", "shounin")), [])

    def test_確認の最中は_本番の門を通さない(self):
        k = self.mon()
        k._pf = {"kid": KID}
        self.assertIn("取得可否確認の最中（本番の取得を重ねない）", k.card_mon("tameshi"))


class 予約台帳に許可の跡を残す(PfOki):
    """台帳は一時フォルダの bare repo。**置き場の記録が消えても、台帳の跡で2回目を止める。**"""

    def setUp(self):
        super().setUp()
        self.gh = tempfile.mkdtemp()
        self.bare = os.path.join(self.gh, "VirgoB77", "kujiraya-aite-yoyaku.git").replace("\\", "/")
        os.makedirs(self.bare)
        tk.git(self.bare, "init", "-q", "--bare", "-b", "main")
        tane = os.path.join(self.gh, "tane")
        subprocess.run(["git", "clone", "-q", self.bare, tane], check=True, capture_output=True)
        with open(os.path.join(tane, "README.md"), "w", encoding="utf-8") as f:
            f.write("予約台帳\n")
        tk.git(tane, "add", "-A")
        tk.git(tane, "commit", "-q", "-m", "はじめ")
        tk.git(tane, "push", "-q", "origin", "HEAD:refs/heads/main")
        self.tane = tane
        self.daicho["yoyaku"] = {"repo": tk.YOYAKU_REPO, "hitsuyou": True}
        self.kaku_all()
        tk.git(self.root, "add", "-A")
        tk.git(self.root, "commit", "-q", "-m", "予約台帳つき")
        self.env = self.run_env("a")

    def tearDown(self):
        for r, _, fs in os.walk(self.gh):
            for n in fs:
                os.chmod(os.path.join(r, n), 0o666)
        shutil.rmtree(self.gh, ignore_errors=True)
        super().tearDown()

    def run_env(self, na, hi="2026-09-25", hajime="07:00:05"):
        d = os.path.join(self.gh, "run-" + na)
        if not os.path.isdir(d):
            subprocess.run(["git", "clone", "-q", self.bare, d], check=True, capture_output=True)
        return {"RUN_DATE": hi, "RUN_HAJIME": "%sT%s+09:00" % (hi, hajime), "YOYAKU_DIR": d,
                "YOYAKU_REPO": tk.YOYAKU_REPO, "GITHUB_REPOSITORY": "VirgoB77/" + REPO,
                "GITHUB_RUN_ID": "run-" + na, "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": "kakunin"}

    def yoyaku(self, hi="2026-09-25"):
        subprocess.run(["git", "-C", self.tane, "pull", "-q", "origin", "main"], capture_output=True)
        p = os.path.join(self.tane, "yoyaku", hi, SID + ".json")
        return yomu(p) if os.path.exists(p) else None

    def test_予約に許可IDが載る(self):
        self.kyoka()
        rec = self.mon(run_id="run-a").kakunin(KID)
        self.assertEqual(rec["result"], "完了", rec["stop_reason"])
        self.assertEqual(self.yoyaku()["kakunin"], KID)

    def test_記録が消えても_翌日の2回目は台帳の跡で止まる(self):
        self.kyoka()
        self.mon(run_id="run-a").kakunin(KID)
        shutil.rmtree(self.p("data", "ref", "preflight", "records"))
        os.remove(self.p("data", "ref", "aite-kyou.json"))
        self.env = self.run_env("b", hi="2026-09-26", hajime="05:00:00")
        rec = self.mon(run_id="run-b", now=lambda: tk.jikoku("2026-09-26", "05:00:10")).kakunin(KID)
        self.tomaru(rec, "予約台帳")
        self.assertEqual(self.nise.kita, [])
        self.assertIsNone(self.yoyaku("2026-09-26"))


class 手で走らせる入口(unittest.TestCase):

    def test_知らない引数では何も書かずに止まる(self):
        ne = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mae = os.path.isdir(os.path.join(ne, "data", "ref", "preflight", "records", "_shirenai"))
        for argv in (["--zzz"], [], [KID, "betsu"], ["../x"]):
            with self.subTest(argv=argv):
                r = subprocess.run([sys.executable, "kakunin.py"] + argv, cwd=ne,
                                   capture_output=True, text=True, encoding="utf-8", errors="replace")
                self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(os.path.isdir(os.path.join(ne, "data", "ref", "preflight", "records", "_shirenai")), mae)


if __name__ == "__main__":
    unittest.main()
