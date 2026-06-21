"""プロジェクト・ワークフローのプリセット（テンプレート）
論文執筆や学会発表など、定型フローのタスク雛形。
steps の各要素: {"title": タスク名, "offset_days": 開始からの相対日, "priority": 1-3}
"""

BUILTIN_PRESETS = [
    {
        "name": "論文執筆（原著）",
        "category": "大学院",
        "steps": [
            {"title": "リサーチクエスチョン確定", "offset_days": 0, "priority": 1},
            {"title": "文献レビュー・先行研究整理", "offset_days": 3, "priority": 1},
            {"title": "データ解析", "offset_days": 14, "priority": 1},
            {"title": "Figure / Table 作成", "offset_days": 28, "priority": 2},
            {"title": "Introduction 執筆", "offset_days": 35, "priority": 2},
            {"title": "Methods 執筆", "offset_days": 40, "priority": 2},
            {"title": "Results 執筆", "offset_days": 45, "priority": 2},
            {"title": "Discussion 執筆", "offset_days": 52, "priority": 1},
            {"title": "共著者へドラフト送付", "offset_days": 60, "priority": 1},
            {"title": "リバイス対応", "offset_days": 70, "priority": 2},
            {"title": "投稿先選定・カバーレター", "offset_days": 80, "priority": 2},
            {"title": "投稿", "offset_days": 85, "priority": 1},
        ],
    },
    {
        "name": "学会発表（口演）",
        "category": "大学院",
        "steps": [
            {"title": "演題登録・抄録提出", "offset_days": 0, "priority": 1},
            {"title": "発表データ確定", "offset_days": 14, "priority": 2},
            {"title": "スライド作成", "offset_days": 21, "priority": 1},
            {"title": "発表原稿作成", "offset_days": 28, "priority": 2},
            {"title": "予演会・リハーサル", "offset_days": 35, "priority": 1},
            {"title": "スライド修正", "offset_days": 38, "priority": 2},
            {"title": "当日発表", "offset_days": 42, "priority": 1},
        ],
    },
    {
        "name": "講演・招待講演",
        "category": "仕事",
        "steps": [
            {"title": "依頼内容・対象者の確認", "offset_days": 0, "priority": 1},
            {"title": "構成・アウトライン作成", "offset_days": 7, "priority": 2},
            {"title": "スライド作成", "offset_days": 14, "priority": 1},
            {"title": "リハーサル", "offset_days": 25, "priority": 2},
            {"title": "当日講演", "offset_days": 30, "priority": 1},
        ],
    },
    {
        "name": "結婚式準備",
        "category": "プライベート",
        "steps": [
            {"title": "式場・日程の確定", "offset_days": 0, "priority": 1},
            {"title": "ゲストリスト作成", "offset_days": 14, "priority": 2},
            {"title": "招待状の送付", "offset_days": 30, "priority": 2},
            {"title": "衣装合わせ", "offset_days": 45, "priority": 2},
            {"title": "席次・進行確定", "offset_days": 70, "priority": 1},
            {"title": "最終打ち合わせ", "offset_days": 85, "priority": 1},
            {"title": "当日", "offset_days": 90, "priority": 1},
        ],
    },
    {
        "name": "研究費申請（科研費等）",
        "category": "大学院",
        "steps": [
            {"title": "公募要領の確認", "offset_days": 0, "priority": 1},
            {"title": "研究計画の骨子作成", "offset_days": 7, "priority": 1},
            {"title": "申請書ドラフト作成", "offset_days": 21, "priority": 1},
            {"title": "指導教員レビュー", "offset_days": 35, "priority": 2},
            {"title": "修正・予算計画", "offset_days": 42, "priority": 2},
            {"title": "提出", "offset_days": 50, "priority": 1},
        ],
    },
]
