# Philosophical Skills Audit Report

## Summary
- **Total skills found**: 16 (across 6 school groupings)
- **Branches covered**: Partial coverage of Ethics, Existentialism/Phenomenology, Epistemology (via Pragmatism), Political Philosophy (via Marxism)
- **Branches missing entirely**: Epistemology (systematic), Metaphysics, Philosophy of Mind, Political Philosophy (systematic), Philosophy of Science, Philosophy of Religion, Aesthetics, Logic, Philosophy of Language, Philosophy of Law
- **Schools needing revision**: All 16 (designed for personality analysis, not profiling)
- **Schools ready for profiling use**: 0 (all lack diagnostic markers, probing questions, scoring rubrics)

## Critical Finding

All existing skills were designed for **personality/behavioral analysis through a philosophical lens** (Chinese-language analytical frameworks for assessing individuals using philosophical constructs). They are NOT designed to **detect which philosophical school someone aligns with**. This is a fundamental purpose mismatch:

| Feature | Current Skills | Needed for Profiling |
|---------|---------------|---------------------|
| Purpose | Apply philosopher X's framework TO a person | Detect whether a person ALIGNS WITH school X |
| Language | Chinese (with English terms) | English (with Chinese cross-references) |
| Input | Evidence cards, timeline, events | Conversation, writing, Q&A responses |
| Output | JSON with construct assessments | Weighted percentage breakdown across schools |
| Diagnostic markers | None | Required |
| Probing questions | None | Required |
| Scoring rubric | None | Required |
| Common confusions | None | Required |
| Cross-branch patterns | None | Required |

## Per-Skill Assessment

### Daoism (laozi.md, zhuangzi.md)
- **Branch**: Maps to Ethics + Metaphysics + Epistemology (cross-cutting)
- **Designed for**: Behavioral analysis through Daoist lens
- **Profiling readiness**: NEEDS_ADAPTATION
- **SEP validation**: PARTIAL (improved after prior fixes — now includes Heshanggong/Wang Bi traditions, scholarly debates)
- **Missing for profiling**: Diagnostic markers, probing questions, scoring rubric, common confusions with other Eastern schools

### Confucianism (kongzi.md, mengzi.md)
- **Branch**: Ethics + Political Philosophy (cross-cutting)
- **Designed for**: Behavioral analysis through Confucian lens
- **Profiling readiness**: NEEDS_ADAPTATION
- **SEP validation**: PASS (strong after fixes — includes five virtues, xing shan debate)
- **Missing for profiling**: Diagnostic markers, probing questions, scoring rubric

### Existentialism (sartre.md, kierkegaard.md, heidegger.md)
- **Branch**: Existentialism & Phenomenology (Branch 11)
- **Designed for**: Behavioral analysis through existentialist lens
- **Profiling readiness**: NEEDS_ADAPTATION
- **SEP validation**: PARTIAL (sartre improved with late Sartre; heidegger still missing some later work)
- **Missing for profiling**: Diagnostic markers, probing questions, scoring rubric, absurdism (Camus) absent

### Pragmatism (peirce.md, james.md, dewey.md)
- **Branch**: Maps to Epistemology (Branch 1)
- **Designed for**: Behavioral analysis through pragmatist lens
- **Profiling readiness**: NEEDS_ADAPTATION
- **SEP validation**: PASS (good after fixes — includes categories, experimentalism, truth controversy)
- **Missing for profiling**: Diagnostic markers, probing questions, scoring rubric

### Marxism/Structuralism (marx.md, gramsci.md)
- **Branch**: Maps to Political Philosophy (Branch 5) + Ethics
- **Designed for**: Behavioral analysis through Marxist lens
- **Profiling readiness**: NEEDS_ADAPTATION
- **SEP validation**: PARTIAL (improved with commodity fetishism, passive revolution)
- **Missing for profiling**: Diagnostic markers, probing questions, scoring rubric

### Standalone Schools (nietzsche.md, kantian_ethics.md, utilitarianism.md, stoicism.md)
- **Branch**: Ethics (Branch 2) primarily
- **Designed for**: Behavioral analysis through respective philosophical lens
- **Profiling readiness**: NEEDS_ADAPTATION
- **SEP validation**: PASS for kantian_ethics (duty categories added), PARTIAL for others
- **Missing for profiling**: Diagnostic markers, probing questions, scoring rubric

## Recommendation

**Strategy**: Keep existing skills as-is (they serve their personality analysis purpose). Build a **parallel profiling system** organized by the 12 branches, using the existing content as philosophical background while adding the required profiling infrastructure (diagnostic markers, probing questions, scoring rubrics). Use the SEP-Validated Guide as the primary content blueprint.
