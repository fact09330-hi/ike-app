"""メール画面 — Gmail受信から要返信を抽出し、AI下書きを作成。
個人Gmail対応（Google認証にGmailスコープ追加後）。大学院M365は次フェーズ。
"""
import html
from email.utils import parseaddr

import streamlit as st

import ai_assistant as ai
import gmail_client as gc
import database as db


def _addr_of(em) -> str:
    """メールdictの差出人からメールアドレスだけを小文字で取り出す"""
    return parseaddr(em.get("sender", ""))[1].strip().lower()


# 動作確認用のダミーメール（実メールに触れずに下書き生成を試せる）
DUMMY_EMAILS = [
    {"msg_id": "demo1", "thread_id": "demo1", "subject": "次回カンファレンスの日程調整のお願い",
     "sender": "デモ花子 <demo-hospital@example.com>", "received_at": "6/15 09:12",
     "snippet": "池本先生 お世話になっております。来週のカンファレンスの日程ですが、火曜か木曜でご都合いかがでしょうか。",
     "body": "池本先生\nお世話になっております。\n来週のカンファレンスの日程ですが、火曜か木曜でご都合いかがでしょうか。ご返信お待ちしております。\nデモ花子",
     "source": "hospital", "source_label": "🏥 大学病院", "_demo": True,
     "message_id_header": "", "references": ""},
    {"msg_id": "demo2", "thread_id": "demo2", "subject": "論文ドラフトへのコメント",
     "sender": "指導教員（デモ） <demo-lab@example.com>", "received_at": "6/14 18:40",
     "snippet": "ドラフト拝見しました。Discussionの第2段落について、先行研究との比較を追記してください。",
     "body": "池本君\nドラフト拝見しました。Discussionの第2段落について、先行研究との比較を追記してください。修正版を今週中にお願いします。",
     "source": "grad", "source_label": "🎓 大学院", "_demo": True,
     "message_id_header": "", "references": ""},
    {"msg_id": "demo3", "thread_id": "demo3", "subject": "結婚式の打ち合わせ日程について",
     "sender": "ホテル宴会 <plan@example.com>", "received_at": "6/14 11:05",
     "snippet": "先日はありがとうございました。次回の打ち合わせ候補日をお送りします。",
     "body": "池本様\n先日はありがとうございました。次回の打ち合わせ候補日をお送りします。6/28か7/5でいかがでしょうか。",
     "source": "personal", "source_label": "📨 個人", "_demo": True,
     "message_id_header": "", "references": ""},
]


def render():
    st.markdown("# メール")
    st.caption("受信から「要返信」を抽出し、文体を踏まえた返信下書きを作成（送信はしません）")

    # デモモード中なら、目立つ警告＋実メールに戻るボタンを出す
    if st.session_state.get("email_demo"):
        _demo_inbox()
        return

    # 通常は実メール。下部に小さくデモへの入口を置く
    if not gc.has_gmail_scope():
        _setup_guide()
    else:
        _gmail_inbox()

    st.markdown("---")
    st.caption("動作確認だけしたい場合（実メールに触れずダミーで試す）:")
    if st.button("🧪 デモ（ダミーメール）を開く"):
        st.session_state["email_demo"] = True
        st.rerun()


def _demo_inbox():
    st.warning("⚠️ **デモモードです**。表示中の3件は **ダミー（偽物）** で、あなたの実際のメールではありません。"
               "実メールを見るには下の「実メールに戻る」を押してください。")
    if st.button("◀ 実メールに戻る", type="primary"):
        st.session_state["email_demo"] = False
        st.rerun()
    st.metric("📥 ダミーメール", len(DUMMY_EMAILS))
    ai_note = "🤖 Claude（文体学習）" if ai.is_available() else "💡 ルールベース（雛形）"
    st.caption(f"下書き生成エンジン: {ai_note}")
    for em in DUMMY_EMAILS:
        _email_card(em, None)


# ─────────────── 未設定時のガイド ───────────────
def _setup_guide():
    st.markdown("""
<div class='ai-card'>
<div class='ai-title'>📨 個人Gmail を連携してメール機能を有効化</div>
<div class='ai-item'>受信から「返信が必要なメール」を自動抽出</div>
<div class='ai-item'>送信済みメールの文体を踏まえた返信下書きを生成</div>
<div class='ai-item'>下書きはGmailに保存（送信は必ずあなたの操作で）</div>
</div>
""", unsafe_allow_html=True)

    st.markdown("### 有効化の手順（2ステップ）")
    st.markdown("""
**① Gmail API を有効化**
下記を開き「有効にする」を押す:
""")
    st.code("https://console.cloud.google.com/apis/library/gmail.googleapis.com?project=vivid-brand-451802-k2",
            language=None)
    st.markdown("""
**② 再認証（Gmail権限を追加）**
ターミナルで以下を実行 → ブラウザで Gmail の許可にチェック:
""")
    st.code('cd "ike_app" && python3 setup_google_auth.py', language="bash")
    st.info("完了後、この画面に「同期」ボタンが表示されます。")

    st.markdown("---")
    st.markdown("### 🏫 大学院メール（Microsoft 365）→ Gmail転送方式")
    st.success("✅ M365 から Gmail へ転送する運用にすれば、この個人Gmail連携だけで"
               "大学院メールも処理できます（Microsoft Graph / Azure登録は不要）。")
    st.caption("`.env` の UNIVERSITY_EMAIL_DOMAINS に大学院のドメインを設定すると、"
               "転送されてきた大学院メールに 🏫 バッジが付いて区別できます。")


# ─────────────── Gmail受信 ───────────────
@st.cache_resource(show_spinner=False)
def _client():
    return gc.GmailClient()


def _gmail_inbox():
    try:
        client = _client()
        account = client.email_address
    except Exception as e:
        st.error(f"Gmail接続エラー: {e}")
        return

    st.markdown(f"**接続中:** `{account}`")
    top = st.columns([3.5, 1.5])
    mode = top[0].radio(
        "抽出モード",
        ["recent", "unread", "important"],
        format_func=lambda x: {"recent": "📨 最近30日（自分宛）",
                               "unread": "🔵 未読のみ",
                               "important": "⭐ 重要マーク"}[x],
        horizontal=True, label_visibility="collapsed")
    if top[1].button("🔄 受信を同期", type="primary", use_container_width=True):
        with st.spinner("Gmailから取得中..."):
            st.session_state.email_list = client.list_needs_reply(max_results=30, mode=mode)
            st.session_state.sent_samples = client.get_sent_samples(n=12)
            st.session_state.email_unread = client.unread_count()
        st.success(f"{len(st.session_state.email_list)}件の候補を取得しました")

    emails = st.session_state.get("email_list")
    if emails is None:
        # 未取得でも未読数だけは表示
        unread = st.session_state.get("email_unread")
        if unread is None:
            unread = client.unread_count()
            st.session_state.email_unread = unread
        if unread is not None and unread >= 0:
            st.metric("📬 受信トレイの未読", f"{unread} 件")
        st.info("「🔄 受信を同期」を押すと、実メールから要返信候補を抽出します。")
        return

    # 「対応不要」(スレッド単位) と「差出人を非表示」(アドレス単位) で除外
    dismissed = db.get_dismissed_ids()
    blocked = db.get_blocked_senders()
    emails = [e for e in emails
              if e.get("thread_id") not in dismissed and _addr_of(e) not in blocked]

    # 自作スキルがあれば 要返信判定／並び替え に反映
    skill_on = False
    try:
        import user_skills
        if user_skills.has_email_skill():
            skill_on = True
            emails = [e for e in emails if user_skills.skill_is_needs_reply(e) is not False]
            emails.sort(key=lambda e: -(user_skills.skill_priority_score(e) or 0))
    except Exception:
        pass

    # 未読数と要返信を並べて表示
    unread = st.session_state.get("email_unread", -1)
    mc = st.columns(2)
    mc[0].metric("📬 受信トレイの未読", f"{unread} 件" if unread >= 0 else "—")
    mc[1].metric("📥 要返信候補", len(emails))
    if skill_on:
        st.caption("🧩 自作スキル `skills/email_skill.py` を適用中")
    ai_note = "🤖 Claude（文体学習）" if ai.is_available() else "💡 ルールベース（雛形）"
    st.caption(f"下書き生成エンジン: {ai_note}　·　"
               f"宣伝メールは除外していますが、完全な要返信判定はAI有効化でさらに精度が上がります")

    for em in emails:
        _email_card(em, client)

    # ── 迷惑メールの誤判定チェック ──
    st.markdown("---")
    _spam_check(client)

    # 除外したメールの管理（復元）
    dismissed_list = db.get_dismissed_emails()
    if dismissed_list:
        with st.expander(f"🚫 対応不要にしたメール {len(dismissed_list)}件（復元可）"):
            for d in dismissed_list:
                rc = st.columns([5, 1])
                rc[0].caption(f"{d['subject'][:50]}  ·  {d['dismissed_at'][:16]}")
                if rc[1].button("復元", key=f"undis_{d['thread_id']}"):
                    db.undismiss_email(d["thread_id"]); st.rerun()

    # 差出人を非表示にしたアドレスの管理（復元）
    blocked_rows = db.get_blocked_sender_rows()
    if blocked_rows:
        with st.expander(f"🙅 差出人を非表示にしたアドレス {len(blocked_rows)}件（復元可）"):
            for b in blocked_rows:
                rc = st.columns([5, 1])
                rc[0].caption(f"{b['address']}  ·  {b['blocked_at'][:16]}")
                if rc[1].button("復元", key=f"unblock_{b['address']}"):
                    db.unblock_sender(b["address"]); st.rerun()


_PERSONAL_HINTS = ["様", "さん", "お世話", "ご確認", "お願い", "日程", "ご返信", "拝啓",
                   "先生", "ご都合", "打ち合わせ", "返信", "ご連絡"]
_PROMO_HINTS = ["セール", "クーポン", "当選", "無料", "今すぐ", "限定", "ポイント",
                "キャンペーン", "割引", "プレゼント", "登録", "配信停止", "unsubscribe"]


def _spam_maybe_legit(em) -> bool:
    """迷惑メールフォルダにあるが、本来は迷惑でない可能性が高いか"""
    if em.get("source") in ("hospital", "grad", "univ"):
        return True  # 大学/病院ドメインからの誤判定
    text = (em.get("subject", "") + " " + em.get("body", em.get("snippet", "")))
    has_personal = any(k in text for k in _PERSONAL_HINTS)
    has_promo = any(k.lower() in text.lower() for k in _PROMO_HINTS)
    return has_personal and not has_promo


def _spam_check(client):
    st.markdown("### 🛡 迷惑メールの誤判定チェック")
    st.caption("迷惑メールフォルダを確認し、本来は迷惑でなさそうなメール（大学/病院ドメイン・個人的な文面）を抽出します。")
    if st.button("🛡 迷惑メールをチェック", key="spam_check_btn"):
        with st.spinner("迷惑メールフォルダを確認中..."):
            st.session_state.spam_list = client.list_spam(max_results=25)
    spam = st.session_state.get("spam_list")
    if spam is None:
        return
    flagged = [e for e in spam if _spam_maybe_legit(e)]
    st.markdown(f"迷惑メール **{len(spam)}件** 中、**{len(flagged)}件** が誤判定の可能性")
    if not flagged:
        st.success("✅ 誤って迷惑メールに入っていそうなメールは見つかりませんでした。")
        return
    st.warning("⚠️ 以下は本来の受信トレイにあるべきかもしれません。Gmailで「迷惑メールではない」と確認してください。")
    for e in flagged:
        subj = html.escape(e.get("subject", "")); sender = html.escape(e.get("sender", ""))
        badge = e.get("source_label", "📨 個人")
        with st.container(border=True):
            st.markdown(f"<div class='proj-name' style='font-size:13px'>"
                        f"<span class='chip'>{badge}</span> {subj}</div>"
                        f"<div class='tmeta'>From: {sender} · {e.get('received_at','')}</div>",
                        unsafe_allow_html=True)
            st.caption(e["snippet"][:140])


def _email_card(em, client):
    eid = em["msg_id"]
    label = em.get("source_label", "📨 個人")
    badge_cls = "chip" if em.get("source") in ("hospital", "grad", "univ") else "chip-gray chip"
    src_badge = f"<span class='{badge_cls}'>{label}</span>"
    # 差出人の <addr> 等がHTMLタグ扱いにならないようエスケープ
    subj = html.escape(em.get("subject", ""))
    sender = html.escape(em.get("sender", ""))
    with st.container(border=True):
        st.markdown(
            f"<div class='proj-name' style='font-size:14px'>{src_badge} {subj}</div>"
            f"<div class='tmeta'>From: {sender} · {em.get('received_at','')}</div>",
            unsafe_allow_html=True)
        st.caption(em["snippet"][:160])

        bcols = st.columns([1.3, 1.8, 1.3, 1.6])
        if bcols[0].button("✍️ 下書き生成", key=f"gen_{eid}"):
            with st.spinner("下書きを作成中..."):
                result = ai.generate_reply_draft(em, st.session_state.get("sent_samples", []))
            st.session_state[f"draft_{eid}"] = result["draft"]
        # 対応不要 → このスレッドのみ今後の要返信リストから除外
        if bcols[2].button("🚫 対応不要", key=f"dis_{eid}",
                           help="このメール(スレッド)を今後表示しません"):
            if not em.get("_demo"):
                db.dismiss_email(em.get("thread_id", eid), em.get("subject", ""))
            if st.session_state.get("email_list"):
                st.session_state.email_list = [
                    e for e in st.session_state.email_list if e.get("msg_id") != eid]
            st.rerun()
        # 差出人を非表示 → このアドレスからは今後すべて非表示
        _addr = _addr_of(em)
        if bcols[3].button("🙅 差出人を非表示", key=f"block_{eid}",
                           help=f"{_addr or 'この差出人'} からのメールを今後リストに出しません"):
            if not em.get("_demo") and _addr:
                db.block_sender(_addr, em.get("sender", ""))
            if st.session_state.get("email_list"):
                st.session_state.email_list = [
                    e for e in st.session_state.email_list if _addr_of(e) != _addr]
            st.rerun()

        draft = st.session_state.get(f"draft_{eid}")
        if draft is not None:
            edited = st.text_area("返信下書き（編集可）", value=draft,
                                  key=f"draftedit_{eid}", height=180)
            if bcols[1].button("💾 Gmailに下書き保存", key=f"save_{eid}"):
                if em.get("_demo"):
                    st.success("✅ （デモ）下書き保存をシミュレートしました。実メールではGmailの下書きに保存されます。")
                else:
                    try:
                        client.create_reply_draft(em, edited)
                        st.success("✅ Gmailの下書きに保存しました（送信はしていません）")
                    except Exception as e:
                        st.error(f"保存エラー: {e}")
