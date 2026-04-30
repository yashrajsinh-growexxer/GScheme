**GScheme**
GScheme is a full-stack AI system for discovering, comparing, and understanding Indian government schemes. It has four major layers:

1. data scraping and dataset preparation
2. knowledge base construction for retrieval
3. backend APIs and RAG inference
4. frontend UI, including compare, voice, and multilingual workflows

---

**1. Project Goal**

The project is designed to help users:

- search schemes by name
- discover schemes based on profile details
- ask follow-up questions about one scheme or multiple schemes
- compare up to 3 schemes side by side
- speak their query using voice input
- interact in Indian languages, with translation handled around the RAG pipeline

So the system is not just a search UI. It is a scheme knowledge platform built around structured scraping + vector retrieval + LLM answering.

---

**2. Repository Structure**

Main folders:

- `Scrapper/`  
  Crawls and extracts scheme data from government websites.

- `data/`  
  Stores scraped JSON, enriched JSON, URLs, chunks, and prepared embeddings.

- `rag_pipeline/`  
  Core AI and retrieval system:
  - knowledge base loading
  - chunking
  - embeddings
  - vector storage
  - retriever
  - generator
  - translation
  - compare engine

- `api/`  
  FastAPI backend that exposes REST endpoints to the frontend.

- `frontend/`  
  Next.js application with search, eligibility, compare, chat, and voice UI.

---

**3. Data Scraping Layer**

This starts in `Scrapper/`.

**3.1 URL scraping**
File: [url_scraper.py](/home/growlt382/Project/GScheme/Scrapper/url_scraper.py)

Purpose:
- crawl category pages from `myscheme.gov.in`
- collect scheme names and URLs
- save scheme link lists under `data/schemes_urls`

How it works:
- uses Playwright, because the site is dynamic and paginated
- opens each category listing page
- waits for page stability with browser-based loading logic
- extracts links matching `/schemes/`
- keeps both `scheme_name` and `scheme_url`
- follows pagination and continues until done

This is the first ingestion step: build the list of pages to scrape.

**3.2 Detailed scheme scraping**
File: [data_scraper.py](/home/growlt382/Project/GScheme/Scrapper/data_scraper.py)

Purpose:
- visit each scheme page
- extract structured content
- save JSON per scheme

What it extracts:
- scheme details
- benefits
- eligibility
- application process
- required documents
- references / sources
- FAQs

Technical behavior:
- uses Playwright for page rendering
- uses BeautifulSoup for DOM parsing and structured extraction
- removes noisy UI text with cleaning rules
- identifies section headings and maps them into normalized fields
- handles application process specially, because pages may contain online/offline/both flows
- writes structured JSON files into `data/schemes_data_json/...`

This gives you the raw scheme dataset.

---

**4. Enrichment and Normalized Data Model**

The knowledge base loader lives in:
[dataloader.py](/home/growlt382/Project/GScheme/rag_pipeline/knowledge_base/data_loader.py)

Purpose:
- load scraped JSON
- normalize it into a consistent internal format

Core object:
- `SchemeData`

Important normalized fields:
- `scheme_name`
- `scheme_url`
- `location_name`
- `location_type`
- `category_name`
- text sections
- FAQs
- `filter_metadata`

A stable `scheme_id` is generated from:
- scheme name
- scheme URL

This is important because the project uses that ID everywhere:
- search results
- compare engine
- chat endpoints
- Qdrant payloads

So the loader is the bridge between raw scraped JSON and downstream RAG logic.

---

**5. Chunking Layer**

File: [chunker.py](/home/growlt382/Project/GScheme/rag_pipeline/knowledge_base/chunker.py)

Purpose:
- split long scheme content into retrievable chunks

Why chunking is needed:
- vector retrieval works best on smaller semantic units
- each chunk represents a section of a scheme, not the entire page

Chunk sources:
- details
- benefits
- eligibility
- application process
- FAQs

Important implementation detail:
each chunk text is prefixed with markers like:
- `[Scheme Name]`
- `[Details]`
- `[Eligibility]`

That helps retrieval and grounding, but it also caused noisy text in the compare table earlier, which is why the compare engine now strips those markers before rendering.

Chunk metadata includes:
- scheme id
- scheme name
- scheme URL
- category
- state/location
- chunk type
- chunk index
- optional application mode

This metadata is crucial for filtering, ranking, and later reconstruction.

---

**6. Embeddings and Vector Storage**

**6.1 Embeddings**
File: [embeddings.py](/home/growlt382/Project/GScheme/rag_pipeline/knowledge_base/embeddings.py)

Current embedding model:
- `BAAI/bge-m3`

Embedding style:
- hybrid retrieval
- dense semantic embedding
- sparse lexical weights

Why hybrid matters:
- dense helps meaning-based retrieval
- sparse helps exact keyword and title-style relevance
- combined retrieval is more robust for scheme discovery

**6.2 Vector store**
File: [vector_store.py](/home/growlt382/Project/GScheme/rag_pipeline/knowledge_base/vector_store.py)

Current vector DB:
- Qdrant

Collection:
- `govt-scheme-hybrid`

Stored payload includes:
- scheme ID
- scheme name
- scheme URL
- category
- location
- chunk text
- chunk type
- application mode
- eligibility-related metadata such as age/gender/caste tags

This payload design is what makes:
- filtered discovery
- comparison metadata extraction
- scheme-specific chat
possible.

---

**7. Retrieval Layer**

File: [retriever.py](/home/growlt382/Project/GScheme/rag_pipeline/inference/retriever.py)

This is one of the most important modules.

**7.1 Title search**
Functionality:
- `search_schemes_by_name()`

Behavior:
- this is local title search, not Qdrant-based
- it builds an in-memory search index from normalized scheme data
- it uses text normalization and fuzzy overlap scoring

Examples of normalization:
- `pm` expands toward `pradhan mantri`
- `yojna` can match `yojana`

This is why scheme name search is fast and can work even when title formatting varies.

**7.2 Eligibility/discovery retrieval**
Functionality:
- `discover_schemes()`

Behavior:
- builds a natural-language query from the user profile
- encodes it with hybrid embeddings
- queries Qdrant
- applies metadata filters for age, state, caste, gender, etc.
- if results are too strict, it can relax filters to avoid empty output
- boosts profession-linked categories when relevant

This is the main scheme recommendation engine.

**7.3 Scheme-specific chunk fetch**
Functionality:
- `fetch_scheme_chunks()`

Behavior:
- retrieves all chunks for one selected scheme from Qdrant
- used by:
  - compare engine
  - scheme-specific chat
  - context-building for learn-more flows

Important current behavior:
- there is no local fallback anymore
- if Qdrant is unavailable, this path fails explicitly

That was changed based on your request.

---

**8. RAG Generation Layer**

File: [generator.py](/home/growlt382/Project/GScheme/rag_pipeline/inference/generator.py)

This is the answer generation engine.

LLM:
- Groq-hosted chat model via `langchain_groq`
- current prompt stack is designed to stay grounded in scheme context

Main flows:

**8.1 Discovery summary**
- user submits profile
- retriever returns candidate schemes
- generator summarizes them as a readable recommendation set

**8.2 Scheme-specific chat**
- user clicks “Learn more”
- scheme chunks are fetched for that scheme only
- generator builds a focused context
- user can ask follow-up questions like:
  - eligibility
  - benefits
  - documents
  - application process

**8.3 General chat over multiple schemes**
- used after discovery
- the selected schemes are combined into context
- user asks broader questions across them

Prompting behavior:
- builds system prompts
- includes prior chat history
- trims history if needed
- injects grounded scheme context into the prompt
- streams answers back to the frontend

---

**9. Multilingual Layer**

File: [translator.py](/home/growlt382/Project/GScheme/rag_pipeline/inference/translator.py)

Current state:
- translation uses **Sarvam Mayura**
- IndicTrans2 has been removed from active use

This module does 3 things:

**9.1 Detect prompt language**
It uses:
- script detection first
- `langdetect` fallback after that

Supported mapping includes languages such as:
- Hindi
- Gujarati
- Bengali
- Marathi
- Tamil
- Telugu
- Kannada
- Malayalam
- Punjabi
- Urdu
- Odia

**9.2 Translate user query to English**
Flow:
- user sends prompt in Hindi/Gujarati/etc.
- translator detects source language
- Mayura translates it into English
- RAG retrieval and generation run in English internally

**9.3 Translate final response back into original language**
Flow:
- model produces English answer
- translator converts answer back to the language used in that prompt
- this is per-turn behavior, not fixed per session

So if in one chat:
- prompt 1 is Hindi -> response should be Hindi
- prompt 2 is Gujarati -> response should be Gujarati

That is the intended current workflow.

Config for this is in:
[config.py](/home/growlt382/Project/GScheme/rag_pipeline/config.py)

Important settings:
- `ENABLE_MULTILINGUAL`
- `SARVAM_TRANSLATION_MODEL`
- `SARVAM_TRANSLATION_MODE`
- translation chunk size
- translation timeout

---

**10. Comparison Engine**

File: [compare.py](/home/growlt382/Project/GScheme/rag_pipeline/inference/compare.py)

Purpose:
- convert scheme chunks into structured comparison rows

Compared fields include:
- scheme name
- state
- category
- URL
- details
- eligibility
- benefits
- income cap
- age limits
- required documents
- application mode
- application process
- gender tags
- caste tags

How it works:
1. fetch all chunks for a scheme from Qdrant
2. group them by section type
3. merge text into structured fields
4. extract heuristic values like:
   - income cap
   - age range
   - application mode
   - docs list
5. clean bracketed chunk headers before returning data

If a field is missing:
- it returns `"N/A"`

That gives the frontend clean, side-by-side comparison data.

---

**11. Backend API Layer**

File: [main.py](/home/growlt382/Project/GScheme/api/main.py)

Framework:
- FastAPI

Main endpoints:

- `POST /api/search`  
  Search schemes by name.

- `POST /api/discover`  
  Discover relevant schemes based on user profile.

- `POST /api/discover-summary`  
  Stream a natural-language summary of discovered schemes.

- `POST /api/chat`  
  Scheme-specific chat for one selected scheme.

- `POST /api/general-chat`  
  Chat across multiple schemes.

- `POST /api/compare`  
  Compare 2 or 3 schemes in one request.

- `GET /api/scheme/{scheme_id}/compare-data`  
  Get structured compare data for one scheme.

- `POST /api/stt`  
  Accept audio upload and send it to Sarvam Saaras STT.

The backend also:
- maps internal scheme results into frontend DTOs
- streams chat responses
- catches retrieval/KB failures
- normalizes STT MIME types from browser audio blobs

---

**12. Voice Interface**

Frontend file:
[VoiceRecorder.tsx](/home/growlt382/Project/GScheme/frontend/src/components/ui/VoiceRecorder.tsx)

Backend route:
`/api/stt` in [main.py](/home/growlt382/Project/GScheme/api/main.py)

STT provider:
- Sarvam Saaras

Workflow:
1. user clicks mic
2. browser requests microphone access
3. `MediaRecorder` records audio
4. UI shows recording state so user knows to speak
5. user stops recording
6. blob is sent to backend
7. backend forwards it to Sarvam
8. transcript is returned
9. transcript is inserted into the input box

Current STT modes used:
- `transcribe` for chat prompts
- `translit` for search-by-name inputs

Why `translit` is important:
- speaking a scheme name in Hindi/Gujarati may otherwise produce native script text
- but your scheme names in the database are English
- so transliteration gives Romanized text that matches search better

This was a practical product decision for search success.

---

**13. Frontend Application**

Framework:
- Next.js App Router
- React
- TypeScript

Main pages:

**13.1 Homepage**
File: `frontend/src/app/page.tsx`

Purpose:
- landing surface for search/discovery
- includes compare button
- includes search/voice entry point

**13.2 Search page**
File: `frontend/src/app/search/page.tsx`

Purpose:
- search schemes by name
- open “Learn more” modal
- ask scheme-specific questions

**13.3 Eligibility page**
File: `frontend/src/app/eligibility/page.tsx`

Purpose:
- profile-based discovery
- user enters demographic / eligibility details
- results feed into summary and chat

**13.4 Compare page**
File: `frontend/src/app/compare/page.tsx`

Purpose:
- compare up to 3 schemes side by side
- OpenRouter-style UI inspiration
- starts with 2 empty selectors
- third selector appears after 2 schemes are chosen

---

**14. Frontend Components**

**Navbar**
File: [Navbar.tsx](/home/growlt382/Project/GScheme/frontend/src/components/layout/Navbar.tsx)

Contains:
- brand
- top navigation links
- compare navigation entry
- route-aware UI behavior

**ChatPanel**
File: [ChatPanel.tsx](/home/growlt382/Project/GScheme/frontend/src/components/chat/ChatPanel.tsx)

Purpose:
- used in scheme-specific modal chat
- starts with summary of the selected scheme
- supports follow-up questioning
- uses streaming
- includes voice recording

**GeneralChatPanel**
File: [GeneralChatPanel.tsx](/home/growlt382/Project/GScheme/frontend/src/components/chat/GeneralChatPanel.tsx)

Purpose:
- used after discovery to talk across multiple schemes

**SchemeSelector**
File: `frontend/src/components/compare/SchemeSelector.tsx`

Purpose:
- searchable scheme picker for compare page
- debounced scheme search
- loads compare data for selected schemes

**ComparisonGrid**
File: `frontend/src/components/compare/ComparisonGrid.tsx`

Purpose:
- render structured rows for side-by-side comparison
- supports 2–3 scheme columns
- shows `N/A` where fields are unavailable

**Modal**
File: `frontend/src/components/ui/modal.tsx`

Current behavior:
- simplified header
- only `Close` button remains
- duplicate Back / X controls were removed

---

**15. Frontend API Client**

File: [api.ts](/home/growlt382/Project/GScheme/frontend/src/lib/api.ts)

Purpose:
- central client for all backend calls

Handles:
- search
- discovery
- scheme chat
- general chat
- compare
- compare-data fetch
- audio transcription

It also supports:
- streaming fetch for chat responses
- error extraction from backend responses
- typed interfaces for scheme and compare data

---

**16. Learn More Workflow**

Current behavior when user clicks “Learn more” on a scheme:
1. selected scheme metadata is passed into modal/chat panel
2. scheme summary is generated
3. user can ask detailed questions
4. backend fetches all chunks for that scheme from Qdrant
5. generator answers based only on that scheme’s context

You also wanted the scheme URL to appear at the top with the scheme name.  
Backend support for this is already present because `SchemeResponse` includes `url`, and the API mapper fills it from `scheme_url`. The frontend modal can therefore show both scheme name and URL without needing a new backend change.

---

**17. End-to-End Workflows**

**A. Search by scheme name**
1. user types or speaks a scheme name
2. frontend calls `/api/search`
3. backend uses local title index search
4. results return with name, state, category, description, score, and URL
5. user opens a scheme or compares it

**B. Eligibility discovery**
1. user enters profile information
2. backend builds hybrid retrieval query
3. Qdrant returns candidate schemes
4. backend maps them into API responses
5. summary and chat are generated over those results

**C. Scheme-specific chat**
1. user clicks Learn more
2. initial summary is generated
3. user asks follow-up question
4. if non-English, prompt is translated to English
5. chunks for that scheme are fetched from Qdrant
6. LLM answers in English internally
7. response is translated back to the original prompt language
8. frontend streams or displays answer

**D. Voice query**
1. user taps mic
2. speaks
3. STT returns transcript
4. transcript fills input
5. user edits or sends it
6. normal search/chat flow continues

**E. Compare**
1. user opens `/compare`
2. selects 2 schemes
3. third slot appears optionally
4. frontend fetches structured compare data
5. grid renders normalized rows with `N/A` for missing fields

---

**18. Current Technical Strengths**

What is already strong in this project:

- structured scraping instead of raw page dumping
- stable scheme ID generation
- hybrid dense+sparse retrieval
- metadata-aware scheme filtering
- dedicated scheme-specific context building
- side-by-side compare architecture
- voice input integrated into multiple screens
- multilingual wrapper around the RAG flow
- separation of concerns between scraping, KB building, retrieval, generation, backend, and UI

---

**19. Current Dependencies / Failure Points**

A few important operational realities:

- `fetch_scheme_chunks()` depends on Qdrant being reachable
- multilingual translation depends on Sarvam Mayura
- voice transcription depends on Sarvam Saaras
- generation depends on Groq API availability
- search-by-name is English-title-oriented, so transliterated input works better than native-script title search unless you add alias handling

So the system is robust in design, but still cloud-dependent for:
- translation
- STT
- generation
- vector retrieval

---

**20. What This Project Has Become**

At this point, GScheme is not just a scraped dataset plus chatbot. It is a multi-module AI product with:

- web scraping and structured extraction
- normalized scheme knowledge modeling
- hybrid vector retrieval
- profile-driven scheme recommendation
- grounded scheme Q&A
- multilingual translation around RAG
- voice-to-text interaction
- scheme comparison UI and API

It’s a fairly complete applied RAG product aimed at a real public-information domain.