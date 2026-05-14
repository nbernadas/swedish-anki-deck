# Swedish A1–C2 Anki Deck

A large-scale Swedish learning project built around frequency-based vocabulary acquisition, automated linguistic enrichment, AI-generated contextual examples, and neural text-to-speech synthesis.

This repository contains the resources, data structure, and methodology behind a Swedish learning deck designed for use with Anki, covering vocabulary from CEFR levels A1 to C2.

---

# What is Anki?

[Anki](https://apps.ankiweb.net/) is an open-source spaced repetition learning platform used for long-term memorization.

Unlike traditional flashcards, Anki schedules reviews dynamically using a spaced repetition algorithm (SRS), increasing intervals for cards you remember well and decreasing them for cards you struggle with. This makes it especially effective for language learning, medicine, engineering, and other knowledge-heavy disciplines.

Anki decks are composed of:
- **Notes** → structured data entries
- **Cards** → generated review prompts
- **Fields** → customizable data containers
- **Note types** → templates controlling card behavior

This project focuses on building a highly structured and customizable Swedish vocabulary dataset optimized for Anki's SRS workflow.

---

# Project Goals

Most public language-learning decks suffer from several recurring issues:

- inconsistent vocabulary ordering
- missing or low-quality audio
- weak contextual examples
- poor customization support
- duplicated vocabulary
- limited linguistic metadata
- lack of reproducibility
- inconsistent CEFR progression

The objective of this project was to create a more systematic Swedish learning resource while experimenting with:
- automated content generation
- API integration
- neural text-to-speech synthesis
- corpus-based frequency ordering
- language data normalization
- Anki note engineering

---

# Main Features

## Frequency-Based Vocabulary Ordering

Vocabulary is ordered according to the Kelly list derived from the Språkbanken corpus from the University of Gothenburg.

This allows learners to prioritize high-frequency vocabulary before progressively moving toward less common words.

The deck attempts to follow a natural progression roughly aligned with CEFR levels:
- A1
- A2
- B1
- B2
- C1
- C2

---

## Modular Subdeck Organization

The project is divided into multiple specialized subdecks:

- Nouns A1–B2
- Nouns C1–C2
- Verbs
- Particle verbs
- Adjectives
- Adverbs
- Pronouns

This organization allows users to:
- focus on specific grammatical categories
- suspend or reorder content
- customize learning priorities
- isolate weak vocabulary domains

---

## AI-Generated Example Sentences

Contextual example sentences were generated using DeepSeek large language models.

The objective was to:
- provide natural sentence exposure
- reinforce contextual understanding
- improve retention through usage examples
- avoid isolated word memorization

While generated sentences were manually reviewed when possible, some inaccuracies or unnatural phrasing may still exist.

---

## Neural Audio Generation

Audio was generated using:
- HyperTTS
- Microsoft Azure Neural Voices
- Sophie Swedish Voice

The project attempts to provide:
- consistent pronunciation
- native-quality audio
- broad vocabulary coverage
- reduced missing-audio issues commonly found in public decks

---

## Linguistic Enrichment

Additional grammatical information was generated using the Free Dictionary API.

Examples include:
- noun plurals
- verb conjugations
- inflectional metadata

This information aims to reduce ambiguity and improve grammatical intuition during review.

---

# Technical Design

One major design goal was improving note modularity and customization.

Earlier versions stored large amounts of information inside merged fields, making customization difficult.

The note type was later redesigned so that:
- translations
- examples
- audio
- conjugations
- plurals
- metadata

are now separated into independent fields.

This allows:
- easier styling
- card-template customization
- selective field visibility
- cleaner exports/imports
- future automation improvements

---

# Repository Structure

```text
.
├── decks/
├── audio/
├── screenshots/
├── scripts/
├── note_models/
├── docs/
└── releases/
```

---

# Motivation

This project originally started as a personal language-learning experiment.

Over time, it evolved into a larger attempt to combine:
- corpus linguistics
- AI-assisted content generation
- cloud TTS services
- automated enrichment pipelines
- customizable spaced-repetition systems

The goal was not only to study Swedish more efficiently, but also to explore practical applications of:
- APIs
- automation tooling
- NLP-adjacent workflows
- cloud services
- structured educational datasets

---

# Known Limitations

- Some AI-generated example sentences may contain inaccuracies
- Frequency ordering is not perfect across all vocabulary categories
- Certain words may still appear slightly outside their intended CEFR range
- Some grammatical enrichments may contain inconsistencies inherited from external APIs
- Audio coverage may still be incomplete for rare vocabulary

---

# Future Improvements

Potential future work includes:
- automated validation pipelines
- improved sentence quality control
- duplicate detection
- frequency recalibration
- IPA pronunciation support
- multi-dialect support
- additional grammatical metadata
- fully reproducible generation scripts

---

# Disclaimer

This project is intended for educational purposes.

Some resources were generated using third-party APIs and AI systems. Accuracy is not guaranteed, especially for advanced vocabulary or idiomatic expressions.

Users are encouraged to cross-reference vocabulary and grammar with authoritative Swedish sources when necessary.

---

# Acknowledgements

- Anki
- Språkbanken (University of Gothenburg)
- DeepSeek
- HyperTTS
- Microsoft Azure Cognitive Services
- Free Dictionary API

---

# License

This repository is distributed for educational and non-commercial purposes unless otherwise specified.
