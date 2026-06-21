"""クラウド公開時のパスワード保護（ログインゲート）。

st.secrets['app_password'] か 環境変数 IKE_APP_PASSWORD が設定されている時だけ有効。
ローカル（未設定）では何もしない＝従来どおり素通りする。
"""
import os
import hmac

import streamlit as st


def _expected_password():
    # st.secrets には触れない（cloud_bootstrap が app_password→IKE_APP_PASSWORD に展開済み）
    return os.getenv("IKE_APP_PASSWORD", "")


def require_login():
    """パスワードが設定されていればログインを要求。未設定なら素通り（ローカル用）。"""
    # デスクトップ/ローカル起動（native_app.py・widget_app.py・起動.command）は
    # IKE_LOCAL=1 を立てておりゲート不要（自分のMac上なのでパスワード入力は不要）。
    # 公開クラウドだけパスワードで保護する。
    if os.getenv("IKE_LOCAL"):
        return

    pw = _expected_password()
    if not pw:
        return  # 保護なし（ローカル開発）

    if st.session_state.get("_authed"):
        return

    st.markdown("<div style='height:10vh'></div>", unsafe_allow_html=True)
    c = st.columns([1, 1.3, 1])[1]
    with c:
        st.markdown("## 🔒 Ike App")
        st.caption("続けるにはパスワードを入力してください。")
        # st.form で囲むと、入力欄で Enter キーを押しても送信される。
        # （フォーム無しの text_input + button では、PCでEnter→再実行されるが
        #   ボタンは押下扱いにならず「ログインできない」状態になっていた）
        with st.form("_login_form", clear_on_submit=False, border=False):
            entered = st.text_input("パスワード", type="password",
                                    label_visibility="collapsed",
                                    placeholder="パスワード",
                                    key="_login_pw")
            submitted = st.form_submit_button("ログイン", type="primary",
                                              use_container_width=True)
        if submitted:
            if hmac.compare_digest(entered or "", pw):
                st.session_state["_authed"] = True
                st.rerun()
            else:
                st.error("パスワードが違います。")
    st.stop()
