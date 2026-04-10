# Decisions Log

## Decision 001
### Topic
是否重寫現有 thesis evaluator

### Decision
不重寫，只在前面新增 AI evidence / draft / monitor layer

### Why
現有 evaluator 已經把 inventory、margin、EPS、target revision、guidance delay、price confirmation 做成可解釋 state machine，價值很高，不應推翻。

### Trade-off
保留既有 evaluator 代表某些新 leaf / branch 邏輯暫時要映射回舊 signal system，而不是一步到位全面樹化。

---

## Decision 002
### Topic
LLM 是否可以當數值真值來源

### Decision
不可以

### Why
LLM 可做 extraction / explanation，但不能取代 parser / verifier。
高權重數值必須有 provenance 與 verification status。

### Trade-off
工程上較麻煩，但可大幅提高可信度。

---

## Decision 003
### Topic
正式 thesis 是否直接改成全新資料模型

### Decision
不直接推翻現有 ThesisDefinition，而採相容擴充

### Why
可保留現有 thesis JSON 與 evaluator 相容性，降低 migration 風險。

### Trade-off
短期內會有「舊結構 + 新結構並存」的複雜度。

---

## Decision 004
### Topic
是否做 full autonomous agent

### Decision
不做

### Why
產品方向是 analyst operating system，不是黑箱自動投資代理。
高風險變化必須進 review queue。

### Trade-off
少了「全自動」的酷炫感，但得到更高可解釋性與可控性。

---

## Decision 005
### Topic
OpenAlice 的哪些概念值得借

### Decision
借：
- append-only event log
- cron scheduling
- cognitive state 的研究狀態版本

不借：
- evolution mode
- self-modifying production code

### Why
Vestra 需要可稽核、穩定的分析系統，不需要 agent 自我改寫 source code。

---

## Decision 006
### Topic
AlphaMemo 該怎麼定位

### Decision
定位為高價值語義證據來源，不是數值真值來源

### Why
法說摘要、管理層發言、Q&A 對 thesis 很重要，尤其在 specificity / conservatism / omission / timeline shift 上。
但數值仍應以 verifier 為主。

---

## Decision 007
### Topic
實作方式採一次到位還是分 phase

### Decision
採 7 phase incremental rollout

### Why
避免大改造成：
- evaluator 被重寫
- UI 被搞壞
- scope creep
- LLM 越權

### Trade-off
整體開發時間較長，但更可測試、可回退。

---

## Decision 008
### Topic
UI 是否一次顯示完整 tree / evidence / monitor / rerating map

### Decision
不一次全顯示，採 progressive disclosure

### Why
主卡片應只顯示：
- thesis state
- certainty stage
- latest change
- review needed

詳細內容再進 drawer / tree view / evidence ledger。

---

## Decision 009
### Topic
當 Codex 或任一開發 agent 中途換手時如何保持連貫

### Decision
以 repo 內 handoff docs 為準，不依賴 agent 記憶

### Why
未來一定會換 agent，連貫性必須建立在書面狀態與 phase boundary 上，而不是單一模型上下文。

---

## Decision 010
### Topic
Phase 1-5 實作確認與文件同步

### Decision
正式確認 Phase 1-5 已在先前開發中超前完成，並同步所有文件。

### Why
實測程式碼已包含 AlphaMemo 引擎與監控層，但文件仍停留在 Phase 1，導致開發認知斷層。必須將文件對齊真實程式碼進度。

---

## Decision 011
### Topic
Phase 6 監控執行策略

### Decision
將論文監控 (Thesis Monitoring) 從 UI Thread 剝離至背景執行。

### Why
隨著覆蓋標的增加，同步掃描會造成 UI 卡頓。Phase 6 的核心是自動化與背景化，確保 UI 永遠只顯示最新結果，而不是在開啟時才計算。

---

## Decision 012
### Topic
Phase 6 Quota Guard 與優先權防禦

### Decision
背景任務採 `hard_rpd`, `soft_rpd`, `reserve_rpd` 三段式限流，且依賴 Priority (`low`, `medium`, `high`, `critical`) 降級排程。

### Why
背景服務會快速消耗 API token (如 Fugle snapshot, AlphaMemo 摘要)。當觸及 `soft_rpd` 時，直接拋棄 `weekly_peer_check` 等 Low priority 排程，確保 `reserve_rpd` 優先保留給 High/Critical 任務 (如即時法說會接入或 review queue 消化)，大幅增加服務的自癒容錯力。

---

## Decision 013
### Topic
Phase 7 UI Progressive Disclosure 與 AnalystPanel

### Decision
不擴增現有 `CardWindow` 的複雜度，只增加 3 個精簡的小徽章 (badge)。詳細的投資邏輯、樹狀結構、證據帳本與審核佇列統一封裝到一個右鍵開啟的 `AnalystPanel` (使用 Tab 介面分層展示)。

### Why
避免主畫面卡片因過多資訊導致 UI 卡頓或資訊超載。採用 progressive disclosure (漸進式揭露) 模式，不僅讓既有使用者維持簡潔的報價圖表體驗，也讓高手的分析資訊井然有序地統一在單一 Toplevel 面板中。