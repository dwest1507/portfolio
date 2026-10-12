# Changelog

## [1.4.1](https://github.com/dwest1507/portfolio/compare/portfolio-v1.4.0...portfolio-v1.4.1) (2026-10-12)


### Bug Fixes

* **ci:** publish eval results as the eval-publisher GitHub App ([15db05d](https://github.com/dwest1507/portfolio/commit/15db05d52d3958d26efbb2b424319532929f8231))
* **ci:** publish eval results as the eval-publisher GitHub App ([9a31868](https://github.com/dwest1507/portfolio/commit/9a31868a02b07934c2be994ba25b5c03661555c9)), closes [#63](https://github.com/dwest1507/portfolio/issues/63)

## [1.4.0](https://github.com/dwest1507/portfolio/compare/portfolio-v1.3.1...portfolio-v1.4.0) (2026-10-12)


### Features

* **chat:** log visitor questions minimally, with a notice in the chat ([7acd025](https://github.com/dwest1507/portfolio/commit/7acd025639bc6f27ebefcef6079ddbf3fe2690e3)), closes [#79](https://github.com/dwest1507/portfolio/issues/79) [#62](https://github.com/dwest1507/portfolio/issues/62)
* **chat:** one OpenAI client per process in production ([00ab4e4](https://github.com/dwest1507/portfolio/commit/00ab4e4011970e4ca13413a1a4cfcf866c0bf7f3)), closes [#85](https://github.com/dwest1507/portfolio/issues/85)
* **chat:** serve answers from OpenAI gpt-6-luna with a global daily cap ([4400b7e](https://github.com/dwest1507/portfolio/commit/4400b7e36d4149e499d8f6d5b8f0a04e6a8a5c86)), closes [#73](https://github.com/dwest1507/portfolio/issues/73)
* **eval:** add Out-of-Scope Cases and generation fields to the Golden Set ([d29d8f2](https://github.com/dwest1507/portfolio/commit/d29d8f25163220360014d67d3e4d46b88f51506e)), closes [#66](https://github.com/dwest1507/portfolio/issues/66)
* **eval:** answer and judge generation-eval cases concurrently ([39f1075](https://github.com/dwest1507/portfolio/commit/39f1075abc31c022305816e7a9613598dfdb7536))
* **eval:** apply David's Required Fact review and add Jev to the Corpus ([80699af](https://github.com/dwest1507/portfolio/commit/80699af4fb6f565528405000822dcb98cc8e1167)), closes [#68](https://github.com/dwest1507/portfolio/issues/68)
* **eval:** Candidate Arms on ONNX Runtime, and Arm eligibility ([8ca08c9](https://github.com/dwest1507/portfolio/commit/8ca08c911d6d042a2d09660c80b54fc3a526339e)), closes [#75](https://github.com/dwest1507/portfolio/issues/75)
* **eval:** choose the generation model by ADR-0008's rule ([2876c58](https://github.com/dwest1507/portfolio/commit/2876c58837576ca2c76b63e5890b757c4b1f5de5)), closes [#72](https://github.com/dwest1507/portfolio/issues/72)
* **eval:** chunk the Corpus along each source's structure ([989b4ec](https://github.com/dwest1507/portfolio/commit/989b4ecf589c13dd49f6ea2ee86751bfa78a37c9)), closes [#74](https://github.com/dwest1507/portfolio/issues/74)
* **eval:** commit the Groq generation baseline ([213b213](https://github.com/dwest1507/portfolio/commit/213b2137b31f3d3da3e037f233a92cce36abfcd6)), closes [#67](https://github.com/dwest1507/portfolio/issues/67)
* **eval:** David's review of the Judge validation labels ([14ba262](https://github.com/dwest1507/portfolio/commit/14ba262ad75f9c4c13d885de7db9ce46acf649e1)), closes [#70](https://github.com/dwest1507/portfolio/issues/70)
* **eval:** Decline judgment validation, with draft labels ([22413ff](https://github.com/dwest1507/portfolio/commit/22413ffaab8c77231cecbb782ba5b623b213b34c)), closes [#86](https://github.com/dwest1507/portfolio/issues/86)
* **eval:** evaluation overhaul — trustworthy retrieval verdicts, generation eval, OpenAI migration ([2f5d1a2](https://github.com/dwest1507/portfolio/commit/2f5d1a29cad0a7a15795ca78293c078378a89c9d))
* **eval:** evaluation overhaul — trustworthy retrieval verdicts, generation eval, OpenAI migration ([2f5d1a2](https://github.com/dwest1507/portfolio/commit/2f5d1a29cad0a7a15795ca78293c078378a89c9d))
* **eval:** fail the suite on over-broad Relevant Phrases ([589d3c2](https://github.com/dwest1507/portfolio/commit/589d3c218b775423c29cfd28cc82ff2ab765cccd)), closes [#64](https://github.com/dwest1507/portfolio/issues/64)
* **eval:** final Judge measurement is the median of three runs ([72d2df9](https://github.com/dwest1507/portfolio/commit/72d2df966f3ca38537fe4bea5248cedfade81b46)), closes [#81](https://github.com/dwest1507/portfolio/issues/81)
* **eval:** first batch of realistic paraphrase and conceptual cases ([671825a](https://github.com/dwest1507/portfolio/commit/671825a8f1e17c5c92368d37a597ee148c5f73fb)), closes [#80](https://github.com/dwest1507/portfolio/issues/80)
* **eval:** generation fingerprint covers splitter effort and filler cutoff ([6dead1d](https://github.com/dwest1507/portfolio/commit/6dead1d4f0539301f93a914a1fa5c71472ff5a34)), closes [#91](https://github.com/dwest1507/portfolio/issues/91) [#62](https://github.com/dwest1507/portfolio/issues/62)
* **eval:** generation Floors record, fingerprint and recalibrate command ([a4b6151](https://github.com/dwest1507/portfolio/commit/a4b6151367342be20a0d4a70aa3b1c3d20bec362)), closes [#90](https://github.com/dwest1507/portfolio/issues/90) [#62](https://github.com/dwest1507/portfolio/issues/62)
* **eval:** generation gate in CI and the published generation results ([a02e82e](https://github.com/dwest1507/portfolio/commit/a02e82ed9ad4ca6c4204ddd816f276251ef15cb2)), closes [#71](https://github.com/dwest1507/portfolio/issues/71)
* **eval:** generation harness and Groq baseline runner; serve at temperature 0 ([d05f284](https://github.com/dwest1507/portfolio/commit/d05f2847c0d7193f9aaaebaf575de69482c50961)), closes [#67](https://github.com/dwest1507/portfolio/issues/67)
* **eval:** held-out Judge validation sentences and the pass bar ([2828c2c](https://github.com/dwest1507/portfolio/commit/2828c2c0c4f914464ba43f0c73c0b81c799550f0)), closes [#81](https://github.com/dwest1507/portfolio/issues/81)
* **eval:** Jev Judge and generation metrics ([5f27ad8](https://github.com/dwest1507/portfolio/commit/5f27ad84cf26d4ed94695b6d1f01e4e052f4e881)), closes [#69](https://github.com/dwest1507/portfolio/issues/69)
* **eval:** Jev retries that survive concurrency ([0fc1848](https://github.com/dwest1507/portfolio/commit/0fc184808f693b598eb6ac8c37b41fda73e50c70)), closes [#88](https://github.com/dwest1507/portfolio/issues/88) [#62](https://github.com/dwest1507/portfolio/issues/62)
* **eval:** Judge validation set, spread tooling and an OpenAI generator ([060c340](https://github.com/dwest1507/portfolio/commit/060c340d472026438c6f410c26fe79060a4047f4)), closes [#70](https://github.com/dwest1507/portfolio/issues/70)
* **eval:** manual comparison run of Candidate Arms through generation ([6691b03](https://github.com/dwest1507/portfolio/commit/6691b03dce0e5715a21898d26732fbf487b3fdb0)), closes [#77](https://github.com/dwest1507/portfolio/issues/77)
* **eval:** noise-aware Verdict Line with won/lost against the Shipped Arm ([352571b](https://github.com/dwest1507/portfolio/commit/352571bbaff080b825e45f05a9e4f33c2b7cf97a)), closes [#65](https://github.com/dwest1507/portfolio/issues/65)
* **eval:** publish a Latency Band per Arm ([b1ff590](https://github.com/dwest1507/portfolio/commit/b1ff590c3aefb94ba5396355137e4cf1d122fb39)), closes [#76](https://github.com/dwest1507/portfolio/issues/76)
* **eval:** recalibrate the generation gate from the five-run study ([b059ac6](https://github.com/dwest1507/portfolio/commit/b059ac6b213391cb6b57d053a4b85c0aebb90003)), closes [#91](https://github.com/dwest1507/portfolio/issues/91)
* **eval:** Required Facts for every answerable Golden Set case ([95eb1ba](https://github.com/dwest1507/portfolio/commit/95eb1baa70a145f09f09d5de6d1b1c95ba422582)), closes [#68](https://github.com/dwest1507/portfolio/issues/68)
* **eval:** rerun the spread study; a rounding step per metric ([94a7b95](https://github.com/dwest1507/portfolio/commit/94a7b95af55d5e18db14567de62267494600b46b)), closes [#81](https://github.com/dwest1507/portfolio/issues/81)
* **eval:** retrieval Floors record, Recalibration, and ADR-0012 ([ba44611](https://github.com/dwest1507/portfolio/commit/ba44611bc979b29c3c5cfe6a3434b1c518944a56)), closes [#87](https://github.com/dwest1507/portfolio/issues/87)
* **eval:** split sentences into claims and revise Jev's questions ([25ef628](https://github.com/dwest1507/portfolio/commit/25ef6286661a72ee1220537d0095af342c66349d)), closes [#81](https://github.com/dwest1507/portfolio/issues/81)
* **projects:** compact retrieval scoreboard rows, with a key beneath ([1b92b16](https://github.com/dwest1507/portfolio/commit/1b92b1622097fe1d5bfad86102ef4335ee05ddf4))
* **projects:** the retrieval scoreboard shows only shippable arms ([8facaed](https://github.com/dwest1507/portfolio/commit/8facaedb793ae8c79f1146cf95cc0cfafc205496))
* update chatbot documentation, evaluation data, and search indexes with new generation metrics ([7b1e5aa](https://github.com/dwest1507/portfolio/commit/7b1e5aa3e3c247ee577efb0d50ba52c60dcabf53))


### Bug Fixes

* **backend:** disable uvicorn access log so visitor queries can't be linked to IPs ([ec52c90](https://github.com/dwest1507/portfolio/commit/ec52c9092ddd1266ad1c91455b4e19cfeb84db7b))
* **ci:** run uv frozen in CI and keep uv.lock in step with releases ([9945aef](https://github.com/dwest1507/portfolio/commit/9945aefb856eefb7d758d561c0d1531003fb551a)), closes [#63](https://github.com/dwest1507/portfolio/issues/63)
* **corpus:** describe the eval suite's current retrieval configurations ([6970afe](https://github.com/dwest1507/portfolio/commit/6970afe659ba4ac291d22b9e1bef74962d72902f))
* **corpus:** the chatbot runs on OpenAI, not Groq ([f8cc6dc](https://github.com/dwest1507/portfolio/commit/f8cc6dc51833aec678e5ee1628a2574012ee0119))
* **eval:** a declined fair question lowers Fact Recall ([8ec4444](https://github.com/dwest1507/portfolio/commit/8ec44441a7e0948b75fa2443195b4e717e310fd0)), closes [#69](https://github.com/dwest1507/portfolio/issues/69)
* **eval:** match Relevant Phrases only at a word start ([f6fa668](https://github.com/dwest1507/portfolio/commit/f6fa668c554363fe6a1d77e6efe001e68f63c368)), closes [#64](https://github.com/dwest1507/portfolio/issues/64)
* **eval:** repair the predictive-maintenance Relevant Phrases ([c425879](https://github.com/dwest1507/portfolio/commit/c425879668226f54a0b5937dfc0d60a71f7d23e4)), closes [#64](https://github.com/dwest1507/portfolio/issues/64)
* **eval:** repair the serverless-scaling-patterns Relevant Phrases ([88c2d57](https://github.com/dwest1507/portfolio/commit/88c2d57705f477bbf2e70e75ee5ad3ee3c27ec6e)), closes [#80](https://github.com/dwest1507/portfolio/issues/80)
* **projects:** the portfolio chatbot is tagged OpenAI, not Groq ([79fdfce](https://github.com/dwest1507/portfolio/commit/79fdfce7d6fedcf76e784872730ac3664455ba3b))
* **ui:** FadeIn reveals elements taller than ten viewports ([5aecfe9](https://github.com/dwest1507/portfolio/commit/5aecfe907cd311b031a5d1cdf2b6f57de8c1f131))

## [1.3.1](https://github.com/dwest1507/portfolio/compare/portfolio-v1.3.0...portfolio-v1.3.1) (2026-10-06)


### Bug Fixes

* **deps:** bump sharp to 0.35.5 for GHSA-wq5f-xc86-pv6w ([d751b8e](https://github.com/dwest1507/portfolio/commit/d751b8e83567ff46efeadeb4cf10d699d919ed36))

## [1.3.0](https://github.com/dwest1507/portfolio/compare/portfolio-v1.2.2...portfolio-v1.3.0) (2026-10-06)


### Features

* add custom site favicons, app icons, and update gitignore for prep docs ([18b5027](https://github.com/dwest1507/portfolio/commit/18b50271632b3c46cfa3c59cbd09ebd4d221b8f8))
* **frontend:** add DW. favicon and app icons; patch dev dependency vulnerabilities ([fb48ef7](https://github.com/dwest1507/portfolio/commit/fb48ef7480bf5f2d251ce6147b542ead093caa47))

## [1.2.2](https://github.com/dwest1507/portfolio/compare/portfolio-v1.2.1...portfolio-v1.2.2) (2026-09-30)


### Bug Fixes

* **deps:** bump undici for security advisories ([bbd6704](https://github.com/dwest1507/portfolio/commit/bbd67041be6d920636f0c1cc185064bb477d6b87))

## [1.2.1](https://github.com/dwest1507/portfolio/compare/portfolio-v1.2.0...portfolio-v1.2.1) (2026-09-14)


### Bug Fixes

* job title ([2749b5d](https://github.com/dwest1507/portfolio/commit/2749b5dd75ec772b01ed802d98449299e3056c4a))
* new index ([d0e7da2](https://github.com/dwest1507/portfolio/commit/d0e7da28247711b20c31d50ed4468c22c194654a))
* **portfolio:** update project tags, card links, descriptions, and dynamic stats ([c58ccb9](https://github.com/dwest1507/portfolio/commit/c58ccb9bfa50fb74f30bc38e3cda7228e36ae66f))
* **portfolio:** update project tags, card links, descriptions, and dynamic stats ([0da2773](https://github.com/dwest1507/portfolio/commit/0da2773dfec19ab8520090aca665be18ec408091))

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
