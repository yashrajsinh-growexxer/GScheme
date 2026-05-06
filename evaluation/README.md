# QSkim Evaluation

This folder evaluates the current QSkim system without changing the user-facing app.

Implemented metrics:

- `Search Recall@5`
- `Eligibility Precision / Recall`
- `Faithfulness`
- `Hallucination Rate`
- `End-to-end latency`

## 1. Prepare the environment

From the project root:

```bash
cd ~/Project/GScheme
source venv/bin/activate
```

Make sure `.env` contains the same keys required by the app:

```env
QDRANT_URL=...
QDRANT_API_KEY=...
GROQ_API_KEY=...
SARVAM_API_KEY=...
```

For retrieval, eligibility, and generation evaluation, Qdrant must be reachable.
For faithfulness and hallucination evaluation, `GROQ_API_KEY` must be available because an LLM judge is used.
For multilingual latency cases, `SARVAM_API_KEY` must be available.

## 2. Build gold datasets

Use the `*.sample.json` files as references and fill these files:

```text
evaluation/datasets/retrieval_eval.json
evaluation/datasets/eligibility_eval.json
evaluation/datasets/chat_eval.json
evaluation/datasets/latency_eval.json
```

The normal workflow is:

- run a search/discovery manually
- copy the relevant `scheme_id` values from API responses
- manually decide the expected/gold scheme IDs
- add those examples to the dataset files

Start with 20-30 cases per file. That is enough to get useful first numbers.

## 3. Run individual evaluations

Search Recall@5:

```bash
python -m evaluation.run_retrieval_eval \
  --dataset evaluation/datasets/retrieval_eval.json \
  --output evaluation/reports/retrieval_report.json
```

Eligibility Precision / Recall:

```bash
python -m evaluation.run_eligibility_eval \
  --dataset evaluation/datasets/eligibility_eval.json \
  --output evaluation/reports/eligibility_report.json \
  --top-k 10
```

Faithfulness and Hallucination Rate:

```bash
python -m evaluation.run_generation_eval \
  --dataset evaluation/datasets/chat_eval.json \
  --output evaluation/reports/generation_report.json
```

End-to-end latency:

First start the backend:

```bash
python -m uvicorn api.main:app --host 127.0.0.1 --port 8501 --reload
```

Then run:

```bash
python -m evaluation.run_latency_eval \
  --dataset evaluation/datasets/latency_eval.json \
  --output evaluation/reports/latency_report.json \
  --api-base http://127.0.0.1:8501/api
```

Latency datasets can use product-facing endpoint names. For example,
`"/eligibility"` is accepted and automatically mapped to the backend
`"/discover"` API route. Reports include both `endpoint` and `api_endpoint`
so you can see the label you requested and the route that was actually called.

## 4. Run all evaluations

After all dataset files are filled:

```bash
python -m evaluation.run_all
```

If you want to skip the LLM judge cost:

```bash
python -m evaluation.run_all --skip-generation
```

## 5. Metric definitions

`Search Recall@5`

Checks whether at least one expected scheme appears in the top 5 search results.

```text
Recall@5 = successful_search_cases / total_search_cases
```

`Eligibility Precision`

Checks how many recommended schemes are actually eligible according to your gold labels.

```text
Precision = relevant_recommended / total_recommended
```

`Eligibility Recall`

Checks how many truly eligible schemes were retrieved.

```text
Recall = relevant_recommended / total_gold_eligible
```

`Faithfulness`

Uses an LLM judge to compare the generated answer against retrieved scheme context.

```text
Faithfulness = faithful_answers / total_answers
```

`Hallucination Rate`

Uses the same judge result. If unsupported claims are found, that answer is counted as hallucinated.

```text
Hallucination Rate = answers_with_unsupported_claims / total_answers
```

`End-to-end latency`

Measures API request time. For streaming endpoints, it records both:

- time to first chunk
- total response time

## 6. Reports

Reports are written under:

```text
evaluation/reports/
```

Each report contains:

- aggregate metric values
- latency percentiles
- per-case rows
- predictions and expected IDs
- judge output for generation evaluation

Use the per-case rows to debug failures, not only the final average.
