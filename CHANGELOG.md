# Changelog

## [1.2.0](https://github.com/dwest1507/portfolio/compare/portfolio-v1.1.0...portfolio-v1.2.0) (2026-09-13)


### Features

* **eval:** add out-of-vocabulary paraphrase batch and interactive scoreboard breakdown ([2daa074](https://github.com/dwest1507/portfolio/commit/2daa07449ea87dc89e9608e79c6dce15cf8dbb8c)), closes [#38](https://github.com/dwest1507/portfolio/issues/38) [#40](https://github.com/dwest1507/portfolio/issues/40)
* **eval:** curate conceptual synthesis batch, run 5-arm benchmark, and record findings ([ebe7cca](https://github.com/dwest1507/portfolio/commit/ebe7cca7cbe3482b4234dc80322698b59899ee2d)), closes [#38](https://github.com/dwest1507/portfolio/issues/38) [#41](https://github.com/dwest1507/portfolio/issues/41)
* **rag:** add query category support and schema v3 eval pipeline ([578d22c](https://github.com/dwest1507/portfolio/commit/578d22c2e767979bbc2b99bcba1876eab6d0d884)), closes [#38](https://github.com/dwest1507/portfolio/issues/38) [#39](https://github.com/dwest1507/portfolio/issues/39)
* **rag:** categorize golden set to schema v3, fix chunk overlap, and publish 5-arm findings ([b550467](https://github.com/dwest1507/portfolio/commit/b550467e922bac788c1a34ca31ea0225e5c2956a))


### Bug Fixes

* **eval:** publish categoryCounts and report exact category sample sizes in scoreboard ([42f655a](https://github.com/dwest1507/portfolio/commit/42f655a33b92be60017e5a5bf565c6d796b2e1e1))
* **rag:** snap chunk overlap to word boundaries and update chatbot knowledge ([40ee9d1](https://github.com/dwest1507/portfolio/commit/40ee9d1704c3b4c7d1c37cdaa1edb6e007fc511a)), closes [#32](https://github.com/dwest1507/portfolio/issues/32)

## [1.1.0](https://github.com/dwest1507/portfolio/compare/portfolio-v1.0.0...portfolio-v1.1.0) (2026-09-12)


### Features

* bump backend version to 1.0.0, update chatbot documentation, an… ([4f2e3f9](https://github.com/dwest1507/portfolio/commit/4f2e3f9c870c3d121d4f02a5cf3e4703f7bbbd4e))
* bump backend version to 1.0.0, update chatbot documentation, and regenerate search indexes ([127f343](https://github.com/dwest1507/portfolio/commit/127f343065d13c36061080c3575a86798bb3df2c))

## [1.0.0](https://github.com/dwest1507/portfolio/compare/portfolio-v0.4.1...portfolio-v1.0.0) (2026-09-05)


### ⚠ BREAKING CHANGES

* **rag:** evalResults.json is schemaVersion 2 — it gains `split`, and `goldenQuestions` now counts the measured portion rather than the whole set. A v1 document measured all 55 questions and is not comparable with a v2 held-out run. RAGPipeline.retrieve() drops its candidates_k parameter and RAGPipeline.warm() is gone; there are no model weights left to warm.

### Features

* image for portfolio card ([1cd327c](https://github.com/dwest1507/portfolio/commit/1cd327c1303bca5d0a8afd7e404cd7b00d1b8951))
* **rag:** retire the dense and re-ranking stages from production ([0856ea5](https://github.com/dwest1507/portfolio/commit/0856ea5dedaca4ae7516942b1e8f33fded89d4e3)), closes [#23](https://github.com/dwest1507/portfolio/issues/23)


### Bug Fixes

* **rag:** guard the served index, state an empty context, and stop ties reading as wins ([38ea92e](https://github.com/dwest1507/portfolio/commit/38ea92e09a31f1b0e1b205084298b70f36911cc2))

## [0.4.1](https://github.com/dwest1507/portfolio/compare/portfolio-v0.4.0...portfolio-v0.4.1) (2026-09-05)


### Bug Fixes

* **pii:** use fictional contact details in fixtures and docs ([6cd57c6](https://github.com/dwest1507/portfolio/commit/6cd57c6995fa516fded429f27293be6d5464b160))

## [0.4.0](https://github.com/dwest1507/portfolio/compare/portfolio-v0.3.0...portfolio-v0.4.0) (2026-09-05)


### Features

* measure retrieval quality, fix a PII disclosure, and surface the eval suite ([51e139e](https://github.com/dwest1507/portfolio/commit/51e139e69f402e01aea022dec718b685772ff179))


### Bug Fixes

* **eval:** publish only when the measurement moved ([64adaee](https://github.com/dwest1507/portfolio/commit/64adaeec4c67bc3275cf8786cf4ec3a232c84cd5))

## [0.3.0](https://github.com/dwest1507/portfolio/compare/portfolio-v0.2.0...portfolio-v0.3.0) (2026-09-04)


### Features

* link to new baby names app ([65bfbf0](https://github.com/dwest1507/portfolio/commit/65bfbf04b6045afc48eae8e288357b50b5c4c795))

## [0.2.0](https://github.com/dwest1507/portfolio/compare/portfolio-v0.1.0...portfolio-v0.2.0) (2026-08-31)


### Features

* updated link to new nietzsche chatbot ([2719e4b](https://github.com/dwest1507/portfolio/commit/2719e4b19559c13edfd45faf61dd1ebff6b5ef56))

## 0.1.0 (2026-08-30)


### Features

* added images for project cards ([74a1c21](https://github.com/dwest1507/portfolio/commit/74a1c2145bd771b415865ebdd2a9c1fbf6458370))
* automate versioning and releases with Release Please ([#13](https://github.com/dwest1507/portfolio/issues/13)) ([4e3f3f7](https://github.com/dwest1507/portfolio/commit/4e3f3f715113f8532a55825d70e999a58c390fee))
* chatbot widget ([73d9cea](https://github.com/dwest1507/portfolio/commit/73d9cea6d01d1bfb06b5f88b12974fc1bd476904))
* **ci:** production CI/CD pipeline ([76c6719](https://github.com/dwest1507/portfolio/commit/76c67194a3c5d67ed19e0e4e68d2b617ae4fcaa8))
* UI design update ([2a0c44a](https://github.com/dwest1507/portfolio/commit/2a0c44a6e25f6f2ce8f7653a4c4fb72a968a0456))


### Bug Fixes

* **a11y:** WCAG AA fixes from Lighthouse audit ([2f2483b](https://github.com/dwest1507/portfolio/commit/2f2483bfd5258fc6896644657f5a1ef744951b95))
* baby names app link ([fcf1515](https://github.com/dwest1507/portfolio/commit/fcf151504b24e0160390a20182960e44c7ab1ada))
* **backend:** commit the FAISS/BM25 indexes so the image can copy them ([0260665](https://github.com/dwest1507/portfolio/commit/0260665f90d5d2265f4f0c4e5eba624fe91d16b3))
* **backend:** restore chat by making the Groq model configurable ([3b9a5ad](https://github.com/dwest1507/portfolio/commit/3b9a5ad6d8b4a3c3f4dd07417573cb385e56dfb4))
* chatbot ([da37607](https://github.com/dwest1507/portfolio/commit/da37607287b13f35e6d25e5b0e19e37f03fac7ed))
* **ci:** pin Node via .nvmrc so CI matches local npm resolution ([95b686c](https://github.com/dwest1507/portfolio/commit/95b686c272f66f9ff3c20706e8d3500ed81e1137))
* **frontend:** render markdown formatting in assistant chat messages ([e89d6df](https://github.com/dwest1507/portfolio/commit/e89d6dfb1bac4c3f7e611c2cac5beb3c09cbb231))
* links ([1bc6d8a](https://github.com/dwest1507/portfolio/commit/1bc6d8a452d9a3af75675399a66bd3fae8368cd7))
* **make:** make `make dev` work after `make stop && make clean` ([081c8ad](https://github.com/dwest1507/portfolio/commit/081c8ad49023769b343608fadc8fe2517a971f8b))
* restore AI chat (Groq model decommissioned) and repair the make dev loop ([23606df](https://github.com/dwest1507/portfolio/commit/23606dfacb3362a079ca7a0c983c89803dc3da8f))
