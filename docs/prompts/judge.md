# LLM Judge Prompt

**Version:** `judge-v1` (no version number in code yet)  
**Source file:** `app/services/llm_judge.py`  
**Used for:** Weekly quality review — grades the last 50 detections 1-5

---

## Purpose

Runs once a week against recent `detection_audit` rows. Grades extraction quality, flags misses and false positives, and suggests prompt improvements.

---

## Current Prompt

```
You are reviewing the output of a commitment detection model.

Source email:
{source_content}

Model extracted:
{parsed_result}

Evaluate:
1. Were all commitments in this email correctly identified? List any that were missed.
2. Were any extracted items NOT actually commitments? List false positives.
3. Rate extraction quality: 1-5
4. If quality < 4: suggest one specific change to the detection prompt that would improve this case.

Respond in JSON:
{
  "missed": [],
  "false_positives": [],
  "quality_rating": N,
  "prompt_suggestion": "..."
}
```

---

## Known Limitations

- No failure taxonomy — quality issues are classified as "missed" or "false_positive" only. Doesn't distinguish between `owner_resolution_error`, `request_vs_commitment_confusion`, `quoted_text_contamination` etc.
- One suggestion per run — can't capture multiple improvement directions
- Backlogged improvement: upgrade to diagnostic evaluator with failure categories

---

## Threshold

Judge runs weekly. Quality rating < 3.5 triggers a prompt review flag. Currently the prompt is at ~3.2/5 — WO-4 (speech act) is expected to improve this significantly.
