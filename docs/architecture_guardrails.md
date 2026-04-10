# Architecture Guardrails

## Core principle
Vestra 是 thesis-driven analyst operating system，不是黑箱投資判斷機器。

## Non-negotiable rules
1. 不可重寫現有 `thesis_evaluator.py` 核心 state machine
2. 不可讓 LLM 成為數值真值來源
3. 不可移除現有手動 thesis 編輯能力
4. 不可讓高風險狀態變更直接自動生效
5. 不可把新聞 / 社群情緒單獨當成 thesis state 依據
6. 不可把 agent 演進成自我修改 production code 的自治系統
7. 不可在未經 review 的情況下修改 kill conditions
8. 不可破壞現有 `ThesisStore / ThesisDialog / CardWindow` 基本流程

## Preserved existing modules
以下模組預設視為穩定核心，除非必要，不做大改：
- `widget/research/thesis_models.py`
- `widget/research/thesis_store.py`
- `widget/research/thesis_evaluator.py`
- `widget/components/thesis_dialog.py`
- `widget/card_window.py`

## LLM role boundaries
LLM 可以做：
- coverage planning
- tree style routing
- transcript / filing evidence extraction
- management wording classification
- thesis draft generation
- delta explanation

LLM 不可以做：
- 未驗證數值寫入正式 thesis
- 取代 parser / verifier 成為 numeric truth source
- 直接決定正式 thesis state
- 直接覆寫 production evaluator rules

## Numeric truth policy
所有高權重數值必須走 verifier：
- revenue
- gross margin
- inventory
- accounts receivable
- CapEx
- guidance range
- target revision proxy

只有 `verified` 狀態的數值，才可影響高權重 thesis 判斷。

## Review policy
以下情況必須進 review queue：
- 新 thesis 建立
- impact = `weaken`
- impact = `break`
- verification conflict
- 新 critical risk factor
- kill condition 被觸發
- 管理層關鍵敘事轉保守且影響核心 branch

## UI policy
- 主卡片只顯示摘要狀態，不顯示全部細節
- 詳細 evidence 與 tree view 用 progressive disclosure
- 不一次把所有 branches / leaves 塞進主畫面
- 所有高影響 AI 結論都必須可展開看來源

## Data storage policy
正式 thesis 與 AI draft / event log / review queue 分開儲存：
- formal thesis = stable JSON
- drafts = separate folder
- event log = append-only JSONL
- review queue = separate storage
- numeric facts = separate verified registry

## OpenAlice boundary
可借：
- cron scheduling 思維
- append-only event log
- cognitive state 的研究狀態化版本

不可借：
- evolution mode
- self-modifying source code
- unrestricted Bash autonomy in production

## AlphaMemo boundary
AlphaMemo 是高價值語義證據來源，但：
- 不等於數值真值來源
- 不可只做 generic sentiment
- 必須保留原文 quote 與 speaker role
- 需支援 transcript 缺失時的 graceful fallback

## Decision rule
任何 agent 若發現規格衝突：
- 先列出衝突
- 不要自行重構整體架構
- 不要擴張任務範圍