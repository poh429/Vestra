# Issue Triage Guide

## Purpose

這份文件用來把驗證階段發現的問題，快速分成：

- 立刻修
- 下一版修
- 先觀察

目標不是把所有問題都立刻做掉，而是：
- 先保護系統可信度
- 先修會誤導使用者的錯
- 避免 UI 細節把真正重要的問題淹沒

---

## Triage Categories

## P0 — Immediate Fix
必須立刻修，不應等下一版。

適用條件：
- 會誤導 thesis state
- 會誤導 review decision
- 會讓 verified numeric fact 錯誤進入正式流程
- 會造成背景任務失控、重複寫入、漏寫入
- 會造成 UI 卡死或主要功能失效

典型例子：
- kill condition 已觸發卻沒進 review queue
- `weakening / broken` 被誤判成 `intact`
- verified gross margin 數值錯誤
- event log 發生 race condition 導致資料遺失
- AnalystPanel 打不開或主卡片卡住

處理時限：
- 立即建立 issue
- 優先 hotfix
- 未修前不應發新版本

---

## P1 — Next Patch
重要，但不需要中止目前版本。

適用條件：
- 會降低 trustworthiness
- 會讓 evidence / review 有明顯噪音
- 會讓使用者頻繁困惑
- 會讓某一類股票分析品質明顯偏低

典型例子：
- AlphaMemo 的 hedging 偵測對某些公司過度敏感
- tree style routing 對某一類標的常常選錯
- review queue 偶爾產生沒必要的 warning
- market belief gap 常常寫得太空泛
- evidence ledger 可追溯，但展開層級太深

處理時限：
- 下一個 patch / minor release 處理
- 可以帶著已知問題繼續驗證

---

## P2 — Observe
暫時不修，先收集樣本。

適用條件：
- 目前只出現 1–2 次
- 不確定是不是 system bug
- 不確定是否會持續出現
- 有點怪，但未直接傷害決策品質

典型例子：
- 某一檔股票出現奇怪 branch 命名
- 某次 transcript 因格式異常，specificity 沒抓到
- 某個 badge 文案看起來不夠直覺
- 某些 quote 排版不夠漂亮

處理方式：
- 先記錄
- 等累積到 3 次以上再判斷是否升級

---

## P3 — Backlog / Nice to Have
不影響核心品質，可排到後面。

典型例子：
- 顏色或 icon 不夠一致
- tooltip 文案可更精煉
- review queue 可以再更好看
- summary wording 可以更像 sell-side memo

---

## Triage Dimensions

每個 issue 至少都要從以下 5 個面向判斷。

## 1. Impact on Trust
它會不會讓使用者不信系統？

等級：
- High
- Medium
- Low

高 impact 例子：
- 數值錯
- 引文對不上
- 系統說法和證據不一致

---

## 2. Impact on Decision Quality
它會不會影響投資判斷？

等級：
- Critical
- Significant
- Minor
- None

Critical 例子：
- thesis state 錯
- review 任務漏掉
- kill condition 沒亮紅燈

---

## 3. Frequency
它常不常發生？

等級：
- Always
- Often
- Sometimes
- Rare

---

## 4. Scope
影響範圍有多大？

等級：
- System-wide
- One feature
- One workflow
- One symbol / one data source

---

## 5. Recoverability
使用者能不能自己發現或繞過？

等級：
- Hard to recover
- Recoverable with review
- Easy to recover

如果是：
- high trust impact
- high decision impact
- system-wide
- hard to recover

通常就是 P0。

---

## Triage Rules

## Rule 1
只要影響正式 thesis state 或 review queue 正確性，至少是 P1。

## Rule 2
只要 verified numeric fact 錯誤，直接當成 P0。

## Rule 3
只要 evidence 無法追溯 source / quote，至少是 P1。

## Rule 4
如果只是 wording / 排版 / badge 細節，不要升到 P0 或 P1。

## Rule 5
如果目前只是單一 symbol、單一 transcript 的特殊格式問題，先放 P2 觀察，除非它直接影響決策。

---

## Standard Issue Template

每一個 issue 都用這個格式記錄：

### Title
一句話描述問題。

### Category
- P0
- P1
- P2
- P3

### Area
- Tree routing
- Evidence pipeline
- Numeric verification
- AlphaMemo communication engine
- Monitoring
- Review queue
- Scheduler
- UI
- Event log

### Symbol / Scenario
- 哪一檔股票
- 哪個資料事件
- 哪個畫面或流程

### Observed behavior
實際發生什麼。

### Expected behavior
原本應該發生什麼。

### Why it matters
為什麼這個問題重要。

### Classification
- False positive
- False negative
- Structural
- Verification
- UX
- Performance
- Reliability

### Severity dimensions
- Trust impact:
- Decision impact:
- Frequency:
- Scope:
- Recoverability:

### Suggested action
- hotfix
- patch
- observe
- backlog

---

## Quick Triage Matrix

### 立刻修（P0）
符合任一條件就直接進：
- thesis state 錯
- verified numeric fact 錯
- review queue 漏掉 critical event
- event log / queue 資料遺失
- 背景執行導致 UI 卡死

### 下一版修（P1）
符合多數條件：
- 對 trust 有明顯傷害
- 對部分標的會穩定產生噪音
- 會讓使用者常常不確定該不該相信系統
- 但還沒有直接造成致命誤判

### 先觀察（P2）
符合多數條件：
- 低頻
- 單點
- 暫時可被人 review 補救
- 尚未證明是系統性問題

### Backlog（P3）
- 美化
- 微調
- 小優化
- 額外便利功能

---

## Escalation Rules

### P2 → P1
當同類問題在不同 symbol / transcript / workflow 中累積出現 3 次以上。

### P1 → P0
當問題已被證明會誤導：
- thesis state
- review action
- verified numeric interpretation

### P3 → P2
當使用者開始持續反映某個 UX 問題真的影響工作流。

---

## Review Cadence

### Daily
只看：
- P0
- 新的 P1

### Weekly
統整：
- P1
- 重複出現的 P2

### Monthly
回顧：
- 哪些 P2 可以關掉
- 哪些要升級為 P1
- 哪些 P3 值得排進下一版

---

## Release Policy

### Hotfix release
只修 P0，不順手塞其他功能。

### Patch release
優先修 P1，視情況帶少量高價值 P2。

### Minor release
做：
- UX 改善
- model / rule refinement
- AlphaMemo engine 提升
- market belief map 提升

---

## Recommended Storage

建議建立：

`docs/issues/`

每個 issue 一個檔案，例如：

- `docs/issues/2026-04-10-aaoi-false-positive-hedging.md`
- `docs/issues/2026-04-10-nvda-missing-kill-condition-alert.md`

或至少維護一份總表：

`docs/issues/index.md`

---

## Recommended First Labels

如果你未來要搬到 GitHub Issues，建議先固定這些 label：

- `p0`
- `p1`
- `p2`
- `p3`
- `false-positive`
- `false-negative`
- `verification`
- `ux`
- `performance`
- `reliability`
- `alphamemo`
- `monitoring`
- `tree-thesis`
- `review-queue`
- `scheduler`

---

## Final Principle

不要問：
「這是不是 bug？」

先問：
**「這會不會讓使用者更容易做錯判斷？」**

如果答案是會，
那它就不是小問題。