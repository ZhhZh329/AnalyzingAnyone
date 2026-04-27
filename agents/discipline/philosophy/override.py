"""
override.py — Philosophy-specific execution logic.

Custom pipeline behavior for the philosophy discipline agent:
1. post_process: Extract philosophical alignment data, detect cross-branch
   patterns, and produce a unified philosophical profile summary.

The runtime calls these hooks automatically:
- pre_process(context) → modify context before prompt building
- build_prompt(role, context, template, config) → custom prompt building
- parse_response(raw, role) → custom response parsing
- post_process(result) → modify result after parsing
"""

from pathlib import Path

# ── Cross-branch pattern definitions ────────────────────────────

COHERENT_CLUSTERS = {
    "scientific_naturalist": {
        "schools": ["Empiricism", "Physicalism", "Scientific Realism", "Functionalism"],
        "label": "Scientific Naturalist",
        "description": "Unified materialist worldview grounded in empirical science",
    },
    "classical_liberal": {
        "schools": ["Empiricism", "Consequentialism", "Classical Liberalism", "Legal Positivism"],
        "label": "Classical Liberal",
        "description": "Enlightenment tradition: individual rights, empirical reasoning, outcome-focused ethics",
    },
    "continental_critical": {
        "schools": ["Constructivism", "Moral Relativism", "Hermeneutic Phenomenology", "Post-structuralism"],
        "label": "Continental Critical",
        "description": "Anti-foundationalist tradition emphasizing interpretation, power, and context",
    },
    "traditional_religious": {
        "schools": ["Rationalism", "Moral Realism", "Classical Theism", "Natural Law", "Virtue Ethics"],
        "label": "Traditional Religious",
        "description": "Classical theistic tradition: reason, objective morality, natural law",
    },
    "pragmatic_progressive": {
        "schools": ["Pragmatism", "Virtue Ethics", "Care Ethics", "Egalitarian Liberalism", "Instrumentalism"],
        "label": "Pragmatic Progressive",
        "description": "Dewey-influenced: problem-solving, democratic inquiry, practical ethics",
    },
    "existential_creative": {
        "schools": ["Atheistic Existentialism", "Constructivism", "Expressionism", "Absurdism"],
        "label": "Existential Creative",
        "description": "Freedom-centered: meaning creation, authenticity, artistic expression",
    },
    "analytic_systematic": {
        "schools": ["Classical Logic", "Referentialism", "Scientific Realism", "Functionalism"],
        "label": "Analytic Systematic",
        "description": "Russell/early Wittgenstein tradition: precision, logic, formal analysis",
    },
    "eastern_holistic": {
        "schools": ["Daoism", "Confucianism", "Buddhism", "Virtue Ethics"],
        "label": "Eastern Holistic",
        "description": "Non-Western integrative tradition: harmony, relational ethics, non-dual awareness",
    },
}

KNOWN_TENSIONS = [
    {
        "pair": ("Physicalism", "Moral Realism"),
        "description": "If everything is physical, how can moral facts be objective?",
    },
    {
        "pair": ("Hard Determinism", "Moral Responsibility"),
        "description": "If all events are determined, how can people be morally responsible?",
    },
    {
        "pair": ("Empiricism", "Moral Realism"),
        "description": "You can't observe moral facts — so how can an empiricist be a moral realist?",
    },
    {
        "pair": ("Scientific Realism", "Paradigm Theory"),
        "description": "If science shifts paradigms, how can current theories be 'true'?",
    },
    {
        "pair": ("Consequentialism", "Individual Rights"),
        "description": "Maximizing utility can violate individual rights.",
    },
    {
        "pair": ("Classical Theism", "Hard Determinism"),
        "description": "If God determines all, how can humans have free will?",
    },
    {
        "pair": ("Classical Logic", "Dialetheism"),
        "description": "Can contradictions be true? Accepting dialetheism undermines classical inference.",
    },
    {
        "pair": ("Constructivism", "Natural Law"),
        "description": "If truth is constructed, how can natural law be objective?",
    },
]


# ── Post-processing hook ────────────────────────────────────────

def post_process(result: dict) -> dict:
    """
    Enrich the standard discipline output with philosophy-specific metadata.

    Adds:
    - philosophy_meta.alignment: extracted from emergent philosophical_alignment
    - philosophy_meta.sophistication: extracted from emergent philosophical_sophistication
    - philosophy_meta.detected_schools: flat list of detected school names
    - philosophy_meta.cluster_matches: which coherent clusters this person matches
    - philosophy_meta.tension_flags: which known tensions are present
    """
    if not isinstance(result, dict):
        return result

    meta = {}
    emergent = result.get("emergent_constructs", [])

    # Extract philosophical alignment percentages
    for ec in emergent:
        dim = ec.get("dimension_name", "")
        finding = ec.get("finding", "")

        if "philosophical_alignment" in dim.lower() or "alignment" in dim.lower():
            meta["alignment_raw"] = finding
            meta["alignment_lens"] = result.get("lens", "")

        if "sophistication" in dim.lower():
            meta["sophistication"] = finding

        if "thinker" in dim.lower() or "echo" in dim.lower():
            meta["historical_echo"] = finding

        if "tension" in dim.lower() or "cross_branch" in dim.lower():
            meta["cross_branch_note"] = finding

    # Collect all school names mentioned in findings
    all_text = ""
    for c in result.get("constructs", []):
        all_text += " " + c.get("finding", "") + " " + c.get("assessment", "")
    for ec in emergent:
        all_text += " " + ec.get("finding", "")

    detected_schools = []
    # Check against known school names from all branches
    school_names = [
        "Rationalism", "Empiricism", "Pragmatism", "Skepticism", "Foundationalism",
        "Coherentism", "Reliabilism", "Constructivism",
        "Virtue Ethics", "Deontology", "Consequentialism", "Utilitarianism",
        "Care Ethics", "Contractarianism", "Moral Realism", "Moral Relativism",
        "Emotivism", "Natural Law",
        "Idealism", "Physicalism", "Dualism", "Monism", "Compatibilism",
        "Hard Determinism", "Libertarian Free Will",
        "Functionalism", "Identity Theory", "Eliminative Materialism",
        "Panpsychism", "Property Dualism",
        "Classical Liberalism", "Egalitarian Liberalism", "Libertarianism",
        "Conservatism", "Socialism", "Communitarianism",
        "Scientific Realism", "Falsificationism", "Paradigm Theory",
        "Instrumentalism", "Constructive Empiricism",
        "Classical Theism", "Deism", "Atheism", "Agnosticism", "Fideism",
        "Process Theology", "Religious Pluralism",
        "Formalism", "Expressionism", "Institutionalism",
        "Aesthetic Subjectivism", "Aesthetic Objectivism", "Sublime",
        "Classical Logic", "Intuitionistic Logic", "Fuzzy Logic",
        "Paraconsistent Logic", "Dialetheism",
        "Verificationism", "Ordinary Language", "Referentialism",
        "Speech Act Theory", "Structuralism", "Post-structuralism",
        "Atheistic Existentialism", "Theistic Existentialism", "Absurdism",
        "Phenomenology", "Hermeneutic Phenomenology",
        "Legal Positivism", "Legal Realism", "Critical Legal Studies",
        "Dworkinian Interpretivism",
        "Daoism", "Confucianism", "Buddhism",
        "Stoicism",
    ]
    for school in school_names:
        if school.lower() in all_text.lower():
            detected_schools.append(school)
    meta["detected_schools"] = detected_schools

    # Match against coherent clusters
    cluster_matches = []
    for cluster_id, cluster in COHERENT_CLUSTERS.items():
        overlap = set(detected_schools) & set(cluster["schools"])
        if len(overlap) >= 2:
            cluster_matches.append({
                "cluster": cluster["label"],
                "description": cluster["description"],
                "matching_schools": list(overlap),
                "strength": len(overlap) / len(cluster["schools"]),
            })
    cluster_matches.sort(key=lambda x: x["strength"], reverse=True)
    meta["cluster_matches"] = cluster_matches

    # Check for known tensions
    tension_flags = []
    detected_set = set(s.lower() for s in detected_schools)
    for tension in KNOWN_TENSIONS:
        a, b = tension["pair"]
        if a.lower() in detected_set and b.lower() in detected_set:
            tension_flags.append({
                "schools": list(tension["pair"]),
                "description": tension["description"],
            })
    # Also check via assessment text for implicit tensions
    for tension in KNOWN_TENSIONS:
        a, b = tension["pair"]
        if (a.lower() in all_text.lower() and b.lower() in all_text.lower()
                and tension not in [t for t in tension_flags]):
            # Only add if both terms appear in the analysis text
            already = any(
                set(t["schools"]) == set(tension["pair"]) for t in tension_flags
            )
            if not already:
                tension_flags.append({
                    "schools": list(tension["pair"]),
                    "description": tension["description"],
                    "source": "implicit",
                })
    meta["tension_flags"] = tension_flags

    # Attach metadata to result
    result["philosophy_meta"] = meta

    return result
