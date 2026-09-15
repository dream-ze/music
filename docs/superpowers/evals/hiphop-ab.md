# hip hop 输入链 A/B 评测记录

## 流程

1. 固定 seed：`1001`、`1002`、`1003`。同一段词（`server/inspirations.py` 的「深夜的中英说唱」）。
2. 每次只改一个变量：caption 骨架 / 断行 / `vocal_language`（`zh` vs `unknown`）/ `ACESTEP_SHIFT`（3.0 vs 1.0）。
3. 提交（把 `<preset>` 换成 `hiphop.boom_bap` 或 `hiphop.trap`）：

   ```bash
   set -a; . ./.env; set +a
   curl -s -X POST http://localhost:8000/api/generate \
     -H "Content-Type: application/json" -H "X-Passcode: $APP_PASSCODE" \
     -d '{"lyrics": "...", "feeling": "hip hop 说唱，男声，夜晚城市，中英混合", "length": "short",
          "seed": 1001, "instrumental": false, "overrides": {"preset": "<preset>"}}'
   ```
4. 从 `backend.log` 抽取 DiT 实际收到的 caption / bpm / keyscale（LM CoT 段 `<|im_start|>assistant` 之后），与我们传入的对照。
5. 两人独立打分（1–5）取均值。

## 记录

| 日期 | seed | preset | 变量 | 我们传入的 caption(摘) | LM 产出 caption(摘) | bpm/key | 吐字 | 音色 | 风格 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-14 | 随机 | (无,基线) | 修复前基线 | `Hip Hop, Rap, 中文说唱, 夜晚…`(DeepSeek 标签串,半中文) | "A smooth, bilingual hip-hop track built on a relaxed lo-fi beat…" | 88 / — | | | | 歌词整理回退(空响应);0.6B LM |
| 2026-09-15 | 1001 | hiphop.boom_bap | 新输入链(批次 A–D 首跑) | "A 90s boom bap hip-hop track built on dusty drum breaks, upright bass, jazzy piano samples, vinyl crackle…88 BPM minor-key"(DeepSeek 英文整句,use_cot_caption=False) | 同上(LM 未改写,原样透传) | 88 / F minor | | | | 歌词整理回退(DeepSeek thinking 耗尽预算→空正文),用确定性切分;0.6B LM;mp3 489e4bdb |
| 2026-09-15 | 1001 | hiphop.boom_bap | + DeepSeek 关思考 → 歌词整理走通(DeepSeek 断行) | "A 90s boom bap hip-hop track built on dusty drum breaks, upright bass, jazzy piano samples and vinyl crackle…90 BPM in F minor" | 同上(LM 未改写) | 90 / F minor | | | | 两阶段 ok;每行 6–10 音节,英文短语保持完整;⚠ planner 非确定性:caption/bpm 与上一行略有差异,非单变量对照;mp3 b1441b4c |
