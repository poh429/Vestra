# Validation Playbook

## Purpose

這份文件用來驗證 Vestra Analyst OS v1 在真實使用情境下是否：
- 有用
- 可信
- 不吵
- 不會把使用者帶偏

重點不是 demo 成功，而是系統在真實標的、真實法說、真實資料更新下，能否穩定產出：
- 可追溯的 evidence
- 合理的 tree-thesis
- 有用的 review 任務
- 正確的 thesis state 變化
- 清楚但不過載的 UI

---

## Validation Goals

本階段要驗證 5 件事：

1. **Tree routing 是否合理**
   - formula / process / x_vs_non_x 有沒有選對

2. **Evidence quality 是否夠高**
   - 抽到的 evidence 有沒有真正支持或削弱 thesis
   - quote 與來源是否可追溯

3. **Management communication engine 是否有資訊含量**
   - specificity / timeline / hedging / omission / qna directness 是否有用
   - 是否過度產生噪音

4. **Monitor / review queue 是否不打擾**
   - 該提醒時提醒
   - 不該提醒時不要一直叫

5. **UI 是否可理解**
   - 使用者能不能快速知道：
     - thesis 現況
     - 最近發生什麼
     - 為什麼要 review
     - 哪個 kill condition 接近被觸發

---

## Validation Universe

至少挑 6 到 10 檔，覆蓋不同類型：

### A. Formula 型
適合平台、廣告、SaaS、支付
- 驗證 top question 與 branch 是否能拆成公式型結構

### B. Process 型
適合新品放量、擴產、工業 ramp、電池、生技
- 驗證 milestone / timeline / kill condition 是否清楚

### C. X vs Non-X 型
適合 commodity、記憶體、航運、石油、供需型產業
- 驗證供需分枝是否自然、是否完整

### D. 高估值成長股
- 驗證 market belief gap / rerating trigger 是否真的有洞察

### E. Turnaround / Recovery 股
- 驗證 timing miss 與 thesis break 是否有被區分

### F. 管理層敘事很重要的公司
- 驗證 AlphaMemo communication engine 的價值

---

## Validation Scenarios

每一檔標的至少驗以下情境：

### Scenario 1 — Initial thesis build
檢查：
- top question 是否可回答 yes/no
- tree style 是否合理
- branches 是否清楚
- leaves 是否可操作
- 每片 leaf 是否有 kill condition

### Scenario 2 — Evidence ingestion
檢查：
- evidence 是否有 source / quote / date
- 數值 evidence 是否走 verifier
- 非數值 evidence 是否只進 provisional / accepted 流程
- evidence ledger 是否可讀

### Scenario 3 — Transcript / management update
檢查：
- specificity shift 是否抓得到
- timeline shift 是否抓得到
- more conservative / hedging 是否過度敏感
- omission signal 是否有意義
- speaker role split 是否有幫助

### Scenario 4 — Monitoring event
檢查：
- 新資料進來後是否正確映射到 leaf / branch
- impact 是否合理：confirm / delay / weaken / break / none
- review queue 是否只在需要時才建立任務

### Scenario 5 — UI inspection
檢查：
- 主卡片是否簡潔
- AnalystPanel 是否可理解
- Tree view 是否真的有助於理解
- Evidence ledger 是否方便追溯
- Review queue 是否可操作

---

## Per-Symbol Validation Checklist

每檔股票驗證時，照以下順序記錄：

### 1. Basic
- Symbol:
- Company type:
- Chosen tree style:
- Validation date:
- Reviewer:

### 2. Initial build quality
- Top question clear? `yes / no`
- Tree style fit? `good / acceptable / poor`
- Branch clarity? `good / acceptable / poor`
- Kill conditions present? `yes / no`
- Market belief gap useful? `yes / no`

### 3. Evidence quality
- Evidence density: `low / medium / high`
- Source traceability: `poor / acceptable / strong`
- Numeric verification coverage: `low / medium / high`
- Quote usefulness: `poor / acceptable / strong`

### 4. Communication engine quality
- Specificity detection useful? `yes / no`
- Timeline shift useful? `yes / no`
- Hedging signal too noisy? `yes / no`
- Omission signal useful? `yes / no`
- Q&A directness useful? `yes / no`

### 5. Monitor quality
- Event mapping accurate? `yes / no`
- Review queue noise acceptable? `yes / no`
- Wrong escalation observed? `yes / no`

### 6. UI quality
- Main card readable? `yes / no`
- AnalystPanel understandable? `yes / no`
- Evidence ledger usable? `yes / no`
- Review actions intuitive? `yes / no`

### 7. Final reviewer judgment
- Overall usefulness: `1-5`
- Overall trustworthiness: `1-5`
- Would use in real workflow? `yes / no`

---

## Error Taxonomy

所有問題都要歸類，不要只寫「怪怪的」。

### False Positive
系統說有訊號，但其實不重要或判錯。

例：
- 一般保守措辭被誤判成 `more_conservative`
- 正常季節性變動被誤判成 `weakening`

### False Negative
真正重要的變化沒抓到。

例：
- 管理層語氣明顯更保守，但沒有生成 event
- 關鍵 leaf 實際已接近 kill condition，系統沒提醒

### Structural Error
樹本身建錯。

例：
- tree style 選錯
- branch 漏掉主幹
- leaves 寫得太抽象，不能驗證

### Verification Error
數值處理有問題。

例：
- numeric fact 與來源對不上
- verifier 沒擋住 conflict
- 單位或 period 錯誤

### UX Error
資訊有，但人看不懂或操作不順。

例：
- 主卡片資訊過多
- review queue 看不出優先順序
- evidence ledger 太深

---

## Severity Rules

### Critical
- thesis state 被明顯誤判
- kill condition 被忽略
- verified numeric fact 錯誤
- review queue 漏掉 break 級事件

### High
- 錯誤 escalated review
- tree style 明顯不合理
- management communication engine 連續產生高噪音

### Medium
- evidence ledger 可讀但不夠清楚
- rerating trigger 不夠有洞察
- market belief gap 太空泛

### Low
- 標籤文案不夠清楚
- badge / tooltip 呈現小問題
- layout 細節可改善

---

## Metrics to Track

至少記這些數字：

- Thesis build completion rate
- Evidence acceptance rate
- Evidence rejection rate
- Numeric verification success rate
- Review queue volume per symbol per week
- Review queue false positive rate
- Management signal precision (人工判斷)
- Monitor escalation accuracy
- Average time to review
- User trust score
- User usefulness score

---

## Release Gate for v1.1

在進下一版前，至少要達到：

- 至少 6 檔股票完成完整驗證
- 每檔至少經過一次 transcript / event 更新
- 沒有 Critical 級未解決問題
- Review queue false positive rate 可接受
- 使用者願意在真實研究流程中使用

---

## Validation Cadence

### Daily
- 看有無爆量 review queue
- 看有無 scheduler / background error
- 看 event log 是否有異常

### Weekly
- 回顧本週各 symbol 的：
  - evidence quality
  - monitor accuracy
  - communication signal usefulness

### Monthly
- 做一次 validation review
- 把 false positive / false negative 匯總到 issue list
- 決定下一個 patch / minor release

---

## Output Format for Each Validation Run

建議每次驗證寫一份：

`docs/validation_runs/{symbol}_{date}.md`

內容模板：

### Header
- Symbol
- Date
- Reviewer
- Version

### What happened
- New data source
- New transcript?
- New monitoring events?
- Review queue triggered?

### What was correct
- ...

### What was wrong
- ...

### Classification
- False positive / false negative / structural / verification / UX

### Severity
- Critical / High / Medium / Low

### Suggested fix
- ...

---

## Rules for Reviewers

1. 不要因為系統講得很像專業就直接相信
2. 先看 source / quote / numeric verification
3. 先判斷有沒有幫助，再判斷有沒有錯
4. 錯的地方一定要歸類
5. 一律優先記錄「會誤導投資判斷」的錯誤