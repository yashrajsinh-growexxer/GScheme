# QSkim Evaluation

This folder evaluates the current QSkim system without changing the user-facing app.

Implemented metrics:

- `Search Recall@5`
- `Eligibility Precision / Recall`
- `RAG Grounding Score`
- `Answer Correctness Score`
- `Hallucination Risk`
- `End-to-end latency`

## Current Evaluation Results

The following benchmark was run on the current QSkim system using the datasets
under `evaluation/datasets/` and reports under `evaluation/reports/`.

| Metric | Cases | Result | Latency |
| --- | ---: | --- | --- |
| Search Recall@5 | 33 | `0.8788` | p50 `230.95 ms`, p95 `595.02 ms` |
| Eligibility Precision / Recall | 20 | precision `0.93`, recall `0.8717` | p50 `353.02 ms`, p95 `678.37 ms` |
| Chat Answer Evaluation | 32 | grounding `0.8491`, correctness `0.837`, hallucination risk `0.1509` | answer p50 `3302.89 ms`, answer p95 `5178.68 ms` |
| End-to-end API Latency | 30 | avg `782.9 ms` | total p50 `361.51 ms`, total p95 `1980.25 ms`; first chunk p50 `361.51 ms`, p95 `1535.47 ms` |

Summary:

- Search performance is strong: `Recall@5 = 0.8788` means the expected scheme appears in the top 5 results for about 88% of search cases.
- Eligibility recommendation quality is high: `precision = 0.93` shows that most recommended schemes are relevant, while `recall = 0.8717` shows the system retrieves most of the expected eligible schemes.
- Chat quality is solid: `rag_grounding_score = 0.8491` indicates answers are usually well supported by retrieved chunks, and `answer_correctness_score = 0.837` shows generated answers are close to the official reference answers.
- `hallucination_risk = 0.1509` is a non-LLM estimate from grounding gaps. It does not mean 15% of answers are definitely hallucinated; it means about 15% of answer content had weaker retrieved-context support under the embedding-based scoring method.
- Latency is usable for search and eligibility flows, with sub-second p50 values. Chat is slower because it includes retrieval plus LLM generation, with p50 answer latency around `3.3 s`.

Interpretation:

The system is performing well overall. Search and eligibility metrics suggest the retrieval and filtering pipeline is reliable, while the chat metrics show that generated answers remain mostly grounded and close to official references. The main improvement opportunities are in the remaining search misses, recall gaps for eligibility, and reducing chat response latency.

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

For retrieval, eligibility, and chat evaluation, Qdrant must be reachable.
For chat evaluation, `GROQ_API_KEY` is still needed to generate the app answer through the normal RAG pipeline. The default embedding evaluator does not use a second LLM judge call.
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

Chat answer evaluation:

```bash
python -m evaluation.run_generation_eval \
  --dataset evaluation/datasets/chat_eval.json \
  --output evaluation/reports/generation_report.json \
  --mode embedding
```

The default `embedding` mode does not use an LLM judge. It still uses your normal
chat pipeline to generate the answer, then computes two clearer metrics:

- `rag_grounding_score`: blended semantic-unit and whole-answer similarity against retrieved chunks.
- `answer_correctness_score`: full generated-answer similarity against your normalized `reference_answer`.

Add `reference_answer` to each `chat_eval.json` case when you want correctness
scoring. It can be a single string, a list of strings, or a dictionary of
section names to official strings/lists. Without it, the evaluator still reports
RAG grounding.

Optional LLM judge mode is still available:

```bash
python -m evaluation.run_generation_eval \
  --dataset evaluation/datasets/chat_eval.json \
  --output evaluation/reports/generation_llm_report.json \
  --mode llm \
  --delay-seconds 30 \
  --context-chars 2500 \
  --answer-chars 1200 \
  --judge-max-tokens 180
```

Useful flags:

```text
--mode                   embedding or llm. Default: embedding.
--grounding-threshold    Hard support cutoff shown in per-unit debug rows.
--soft-threshold         Similarity where soft support starts counting.
--strong-threshold       Similarity where soft support becomes full support.
--global-weight          Weight given to whole-answer context similarity.
--max-chunks             Max retrieved chunks used for grounding.
--delay-seconds          Pause after each case. Increase this for large datasets.
--context-chars          Max retrieved context sent to the judge.
--answer-chars           Max generated answer text sent to the judge.
--judge-max-tokens       Max tokens the judge can output.
--max-retries            Number of rate-limit retries per model call.
--retry-buffer-seconds   Extra wait added to Groq's suggested retry time.
--max-wait-seconds       Stop and save progress when Groq asks for a longer wait.
--no-resume              Ignore an existing output report and start again.
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

If you want to skip chat answer evaluation:

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

`RAG Grounding Score`

Splits the generated answer into semantic answer units rather than raw sentences, so markdown headings, numbered lists, and short fragments are merged into more meaningful blocks. It then computes local unit-to-chunk support and blends it with whole-answer-to-context similarity.

```text
RAG Grounding Score =
  (1 - global_weight) * average_soft_unit_support
  + global_weight * whole_answer_context_support
```

`Answer Correctness Score`

Compares the full generated answer with the official `reference_answer` using embedding cosine similarity. The evaluator accepts a string, a list of strings, or a dictionary of section names to official strings/lists, then flattens it into one normalized reference text before scoring.

```text
Answer Correctness Score = cosine(generated_answer_embedding, reference_answer_embedding)
```

`Hallucination Risk`

Uses the improved RAG grounding result as a non-LLM unsupported-risk estimate.

```text
Hallucination Risk = 1 - RAG Grounding Score
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
- sentence-level grounding details for chat evaluation
- generated answer and reference-answer similarity for chat evaluation

Use the per-case rows to debug failures, not only the final average.
