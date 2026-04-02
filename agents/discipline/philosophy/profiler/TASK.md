# Cowork Task: Build a Philosophical Profiling System

## Context

You are building a set of AI skills that analyze a person's philosophical positions across every major branch of philosophy. The user already has some philosophical school skills installed. Your job is to:

1. **Audit** what already exists
2. **Validate** each existing skill against the Stanford Encyclopedia of Philosophy (SEP)
3. **Fix** any skills that are inaccurate or insufficient for profiling people
4. **Expand** systematically to cover all branches and schools
5. **Build** a master orchestrator skill that ties everything together

You have access to the user's Claude API key (it's already configured — no key needed in headers). You can and should use it for validation work.

---

## Phase 0: Understand the Goal

The end product is a **Philosophical Profiler** — a system of skills that can:
- Analyze someone's conversation, writing, or responses to questions
- Determine which philosophical school(s) they align with in each branch
- Produce a weighted percentage breakdown (not binary classifications)
- Surface tensions and cross-branch patterns
- Handle people who are philosophically naive (no jargon) as well as trained philosophers

This is NOT about teaching philosophy. It's about **detecting** philosophical positions from how people think and talk.

---

## Phase 1: Audit Existing Skills

### Step 1.1: Inventory

Find all installed skills related to philosophy. Look in:
- `/mnt/skills/user/` (user-installed skills)
- `/mnt/skills/private/` (private skills)
- Any other skill directories

For each skill found, record:
- Skill name
- Which philosophical branch it covers
- Which schools it includes
- What it's designed to do (teach? analyze? debate?)

### Step 1.2: Assess Fitness for Profiling

**Critical question for each existing skill:** Was it designed to *analyze people's positions*, or was it designed for something else (teaching, debate, explanation)?

A skill designed to *explain* Stoicism is very different from a skill designed to *detect* Stoic tendencies in someone's speech. The profiling system needs the latter.

For each existing skill, evaluate:

```
AUDIT CHECKLIST:
[ ] Does it define each school with enough precision to distinguish it from neighbors?
[ ] Does it include DIAGNOSTIC MARKERS — specific phrases, reasoning patterns, 
    and value expressions that indicate alignment?
[ ] Does it include PROBING QUESTIONS — natural-language questions that differentiate 
    between schools?
[ ] Does it include a SCORING RUBRIC — how to convert signals into weighted percentages?
[ ] Does it flag COMMON CONFUSIONS — schools that look similar but differ in key ways?
[ ] Does it handle HYBRID positions — people who blend schools?
[ ] Is its definition of each school ACCURATE per the Stanford Encyclopedia of Philosophy?
```

### Step 1.3: Validate Against SEP

For EVERY school defined in every existing skill, validate the definition against the Stanford Encyclopedia of Philosophy. Here's how:

```python
# Use the Claude API to do validation
# For each school in an existing skill:

import json

# 1. Fetch the relevant SEP article via web search tool
# 2. Compare the skill's definition against SEP
# 3. Flag discrepancies

validation_prompt = """
I have a skill that defines {school_name} as:
"{skill_definition}"

The Stanford Encyclopedia of Philosophy ({sep_url}) defines it as:
"{sep_definition}"

Compare these two definitions. Identify:
1. Any factual errors in the skill definition
2. Important nuances the SEP mentions that the skill misses
3. Key thinkers the skill gets wrong or omits
4. Whether the skill's definition is precise enough to DISTINGUISH this school 
   from its closest neighbors
5. Rating: ACCURATE / MOSTLY_ACCURATE / NEEDS_REVISION / WRONG
"""
```

Use the Claude API with the `web_search` tool enabled to fetch SEP content:

```javascript
const response = await fetch("https://api.anthropic.com/v1/messages", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    model: "claude-sonnet-4-20250514",
    max_tokens: 4096,
    tools: [{ type: "web_search_20250305", name: "web_search" }],
    messages: [{
      role: "user",
      content: `Search the Stanford Encyclopedia of Philosophy for "${school_name}" 
                and provide: (1) the core definition, (2) key thinkers, 
                (3) main arguments, (4) important distinctions from neighboring positions.
                URL to check: https://plato.stanford.edu/entries/${sep_entry_slug}/`
    }]
  })
});
```

### Step 1.4: Produce Audit Report

After checking all existing skills, produce a structured report:

```markdown
# Philosophical Skills Audit Report

## Summary
- Total skills found: X
- Branches covered: [list]
- Branches missing: [list]
- Schools needing revision: [list]
- Schools ready for profiling use: [list]

## Per-Skill Assessment

### [Skill Name]
- Branch: [branch]
- Schools included: [list]
- Designed for: [teaching / analysis / debate / profiling]
- Profiling readiness: [READY / NEEDS_ADAPTATION / NEEDS_REWRITE]
- SEP validation: [PASS / PARTIAL / FAIL]
- Missing elements: [diagnostic markers / probing questions / scoring rubric / etc.]
- Specific issues: [list of factual errors or missing nuances]
```

Present this report to the user before proceeding.

---

## Phase 2: Fix and Adapt Existing Skills

For each existing skill that needs work:

### If the skill is MOSTLY GOOD but needs profiling adaptation:

Add these sections to the skill's reference file:

```markdown
## Diagnostic Markers
For each school, list phrases and reasoning patterns that indicate alignment.
These must be in PLAIN LANGUAGE — what a non-philosopher would actually say.

## Probing Questions  
5-10 questions per branch that sound natural but differentiate between schools.
Each question should target a specific pair of schools that are easily confused.

## Scoring Rubric
How to convert observed markers into weighted percentages.
Rules:
- Percentages must add to 100% within each branch
- Include confidence level (Low / Moderate / High)
- Allow "Undetermined" if insufficient signal
- Flag contradictions worth surfacing
```

### If the skill has FACTUAL ERRORS per SEP:

Fix each error by:
1. Noting the current (wrong) definition
2. Fetching the correct definition from SEP via API + web_search
3. Rewriting to match SEP while keeping the language accessible
4. Preserving the skill's original name and structure

### If the skill was designed for TEACHING, not PROFILING:

It needs deeper restructuring. The teaching-oriented content (explanations, history, examples) can stay as background context, but add a new top-level section:

```markdown
## Profiling Mode

When analyzing a person's philosophical alignment in this branch:

1. LISTEN for diagnostic markers (see below)
2. ASK probing questions if insufficient signal
3. SCORE alignment as weighted percentages
4. FLAG tensions with other branches
5. NOTE confidence level

### What to Listen For
[diagnostic markers table — plain language phrases mapped to schools]

### What to Ask
[probing questions — natural, conversational, ordered broad-to-narrow]

### How to Score
[rubric — signal types, weights, confidence thresholds]
```

---

## Phase 3: Systematically Add Missing Branches

### The Complete Branch List

The system must cover ALL 12 branches. Check which are missing after the audit:

1. **Epistemology** — How do we know what we know?
2. **Ethics / Moral Philosophy** — What should we do?
3. **Metaphysics** — What is the nature of reality?
4. **Philosophy of Mind** — What is consciousness?
5. **Political Philosophy** — How should society be organized?
6. **Philosophy of Science** — What is science?
7. **Philosophy of Religion** — Does God exist?
8. **Aesthetics** — What is beauty and art?
9. **Logic** — What is valid reasoning?
10. **Philosophy of Language** — How does language relate to meaning?
11. **Existentialism & Phenomenology** — What does it mean to exist?
12. **Philosophy of Law** — What is law?

### For Each Missing Branch, Build a Reference File

Use this process:

#### Step 3.1: Research via API

For each school within the branch, use the Claude API with web_search to fetch the SEP article:

```javascript
// For each school in the branch
const schools = ["virtue-ethics", "ethics-deontological", "consequentialism", ...];

for (const school of schools) {
  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "claude-sonnet-4-20250514",
      max_tokens: 4096,
      tools: [{ type: "web_search_20250305", name: "web_search" }],
      messages: [{
        role: "user",
        content: `Search Stanford Encyclopedia of Philosophy for "${school}". 
                  Extract: (1) core thesis in 2-3 sentences, 
                  (2) key thinkers with dates, 
                  (3) main arguments FOR this position,
                  (4) main objections AGAINST it,
                  (5) how it differs from its closest neighbor positions,
                  (6) important internal variants or sub-schools.
                  Be precise and cite the SEP article.`
      }]
    })
  });
  // Parse and store the result
}
```

#### Step 3.2: Build the Reference File

Each branch reference file follows this template:

```markdown
# [Branch Name]

## SEP Sources
- [list of SEP URLs used]

## Core Question
[The fundamental question this branch addresses]

## Schools of Thought

### [School Name]
- **SEP Source**: plato.stanford.edu/entries/[slug]/
- **Core Thesis**: [2-3 sentence definition, SEP-validated]
- **Key Thinkers**: [names, dates, key works]
- **Main Arguments**: [strongest 2-3 arguments for this position]
- **Key Objections**: [strongest 2-3 arguments against]
- **Diagnostic Markers** (what people say):
  - "[plain language phrase]" → strength: strong/moderate/weak
  - "[plain language phrase]" → strength: strong/moderate/weak
  - "[reasoning pattern description]" → strength: strong/moderate/weak
- **Common Confusions**: 
  - Often confused with [X] because [reason], but differs in [key way]
- **Cross-Branch Correlations**:
  - Often pairs with [school] in [other branch] because [reason]
- **Internal Variants**: [sub-schools if any]

### [Next School]
...

## Spectrum Map
[How schools relate — which are opposites, which are compatible, 
which form a continuum. This prevents binary classification.]

## Probing Questions
Each question targets a specific distinction:
1. "[Natural question]" — distinguishes [School A] from [School B]
2. "[Natural question]" — distinguishes [School C] from [School D]
...

## Scoring Rubric
- Strong signal: Person explicitly argues for the position or uses its key concepts
- Moderate signal: Person's reasoning pattern aligns but without explicit commitment  
- Weak signal: Passing comment or single data point
- Negative signal: Person explicitly rejects this position
- Confidence thresholds:
  - High: 3+ strong signals OR 5+ moderate signals
  - Moderate: 1-2 strong signals OR 3-4 moderate signals
  - Low: Only weak signals
```

#### Step 3.3: Validate Each New File

After writing each reference file, validate it:

```javascript
// Send the entire reference file to Claude with web_search
// Ask it to fact-check every claim against SEP
const validation = await fetch("https://api.anthropic.com/v1/messages", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    model: "claude-sonnet-4-20250514",
    max_tokens: 4096,
    tools: [{ type: "web_search_20250305", name: "web_search" }],
    messages: [{
      role: "user",
      content: `Fact-check this philosophical reference file against the 
                Stanford Encyclopedia of Philosophy. For each school defined, 
                verify: (1) Is the core thesis accurate? (2) Are the key thinkers 
                correct? (3) Are any important nuances missing? (4) Does the SEP 
                flag any cautions about this classification that we should include?
                
                Here is the file:
                ${referenceFileContent}`
    }]
  })
});
```

---

## Phase 4: Build the Master Orchestrator Skill

Once all branch reference files exist and are validated, create the master `SKILL.md`:

```yaml
---
name: philosophical-profiler
description: >
  Analyze a person's philosophical positions across all major branches of
  philosophy. Use this skill when someone wants to discover their philosophical
  alignment, when analyzing text for philosophical positions, when someone 
  expresses views on knowledge, reality, morality, consciousness, politics,
  science, religion, beauty, language, law, or meaning — and wants to understand
  the philosophical tradition behind those views. Also trigger when building
  a "philosophical profile" or when someone asks "what's my philosophy?"
---
```

The master skill should:

1. **Detect which branches are relevant** from the conversation
2. **Load only the needed reference files** (progressive disclosure)
3. **Run analysis** using diagnostic markers from each loaded branch
4. **Aggregate** into a unified profile
5. **Identify cross-branch patterns** (e.g., empiricism + physicalism + scientific realism cluster)
6. **Surface tensions** (e.g., determinist in metaphysics but believes in moral responsibility)
7. **Match to historical thinkers** based on overall pattern

### Profile Output Format

```
══════════════════════════════════════════════════
         PHILOSOPHICAL PROFILE: [Name]
══════════════════════════════════════════════════

SUMMARY
[Natural language description of worldview — 3-5 sentences, 
written like a thoughtful character sketch, no jargon]

BRANCH-BY-BRANCH
[For each branch with sufficient signal:]

  Epistemology (confidence: High)
    Empiricism ............ 50%  ██████████
    Pragmatism ............ 35%  ███████
    Constructivism ........ 15%  ███
    
  Ethics (confidence: Moderate)
    Virtue Ethics ......... 40%  ████████
    Consequentialism ...... 35%  ███████
    Care Ethics ........... 25%  █████

  [etc.]

CROSS-BRANCH INSIGHTS
• [Pattern 1 — consistent worldview cluster]
• [Pattern 2 — interesting tension]
• [Pattern 3 — unexpected combination]

CLOSEST HISTORICAL MATCH
[Thinker name] — [1-2 sentence explanation of why]

OPEN QUESTIONS
[Areas where more information would sharpen the profile]

SEP SOURCES
[List of SEP articles that ground this analysis]
```

---

## Phase 5: Test the System

### Test Cases to Create

1. **The Obvious Utilitarian** — Someone who clearly maximizes consequences in every answer. Should score high consequentialism.

2. **The Hidden Kantian** — Someone who never says "duty" but consistently reasons about universalizability and respect for persons. Tests diagnostic marker quality.

3. **The Contradictory Thinker** — Determinist about free will but strong moral realist. Tests tension detection.

4. **The Philosophically Naive Person** — Uses everyday language, no jargon. Says things like "I just think you should treat people right" and "science tells us how things really are." Tests whether the skill can profile without technical vocabulary.

5. **A Known Philosopher's Writings** — Feed in a passage from, say, John Stuart Mill. The profile should accurately reflect Mill's known positions. This validates accuracy.

6. **The Genuine Pluralist** — Someone who thoughtfully draws from multiple traditions. Tests whether the system avoids forcing people into single boxes.

### How to Test

Use the Claude API to simulate profiling sessions:

```javascript
const testCase = {
  name: "The Obvious Utilitarian",
  statements: [
    "I think we should do whatever produces the most happiness for the most people.",
    "Sometimes you have to sacrifice one person's interests for the greater good.",
    "I judge policies by their outcomes, not their intentions.",
    "Morality is basically about reducing suffering in the world."
  ]
};

const response = await fetch("https://api.anthropic.com/v1/messages", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    model: "claude-sonnet-4-20250514",
    max_tokens: 4096,
    system: masterSkillContent + "\n\n" + ethicsReferenceContent,
    messages: [{
      role: "user",
      content: `Analyze these statements for philosophical alignment in Ethics:
                ${testCase.statements.join("\n")}
                
                Produce a weighted percentage breakdown with confidence level.`
    }]
  })
});
```

### Expected Results

| Test Case | Expected Top Score | Should Also Flag |
|-----------|-------------------|-----------------|
| Obvious Utilitarian | Consequentialism 80%+ | Possible moral realism |
| Hidden Kantian | Deontology 60%+ | Without using the word "duty" |
| Contradictory | Determinism + Moral Realism | TENSION flag between these |
| Naive Person | Should still produce a profile | Lower confidence scores |
| Mill's Writings | Consequentialism + Empiricism + Liberalism | Historical match: Mill |
| Pluralist | No single school >50% | Multiple moderate scores |

---

## Important Design Principles

1. **SEP is the ground truth.** Every school definition must trace back to a specific SEP article. If the SEP says a classification is problematic, the skill must reflect that.

2. **Profiling ≠ Teaching.** The skill detects positions, it doesn't explain them. Explanations are a bonus, not the core function.

3. **No forced classification.** People are messy. Allow blends, tensions, "Undetermined," and low confidence. Forcing someone into a box is worse than admitting uncertainty.

4. **Plain language detection.** Most people don't say "I'm a compatibilist." They say "I think free will and science can both be true." The diagnostic markers must work at the everyday language level.

5. **Charitable interpretation.** Always interpret views in their strongest form before classifying. If someone says something that could be read as naive relativism or thoughtful perspectivism, lean toward the more sophisticated reading.

6. **Surface contradictions gently.** "Your views on free will and moral responsibility create an interesting tension that philosophers have long debated..." — not "You're being inconsistent."

7. **Cultural sensitivity.** This framework is Western-analytic-heavy. When possible, note connections to non-Western traditions (Confucian virtue ethics, Buddhist epistemology, Ubuntu communitarianism, Islamic philosophy, etc.).

8. **The SEP warns against simplistic classification.** Your profiler should too. Include the SEP's own cautions as guardrails in each branch.

---

## Execution Order for Cowork

```
TodoList:
1. [ ] Scan all skill directories for existing philosophical skills
2. [ ] Read each existing skill, catalog what it covers
3. [ ] Validate each skill's definitions against SEP (via API + web_search)
4. [ ] Produce audit report — present to user, wait for feedback
5. [ ] Fix/adapt existing skills based on audit findings
6. [ ] List which branches are still missing
7. [ ] For each missing branch:
   a. [ ] Research all schools via API + web_search against SEP
   b. [ ] Write reference file following the template
   c. [ ] Validate reference file against SEP
   d. [ ] Add diagnostic markers and probing questions
8. [ ] Build master orchestrator SKILL.md
9. [ ] Create test cases (evals.json)
10. [ ] Run test cases via API
11. [ ] Generate eval viewer for human review
12. [ ] Iterate based on feedback
13. [ ] Package final skills
```

---

## File Locations

- Existing skills: Check `/mnt/skills/user/`, `/mnt/skills/private/`, and any paths the user indicates
- Working directory: `/home/claude/philosophical-profiler/`
- Reference files: `/home/claude/philosophical-profiler/references/`
- Test outputs: `/home/claude/philosophical-profiler/workspace/`
- Final output: `/mnt/user-data/outputs/`

If existing skill paths are read-only, copy to the working directory before editing.
