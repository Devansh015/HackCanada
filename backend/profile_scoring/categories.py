"""
Canonical list of technical categories tracked by the Knowledge Map.

Each category has:
  - key   : snake_case identifier (used in dicts / JSON keys)
  - label : human-readable display name
  - group : logical grouping for UI clustering

The CATEGORIES list is the single source of truth.  All other modules
import CATEGORY_KEYS (the list of keys) or CATEGORY_MAP (key → label).
"""

from typing import Dict, List, Tuple

# (key, label, group)
CATEGORIES: List[Tuple[str, str, str]] = [
    # ── Programming Fundamentals ─────────────────────────────
    ("variables",               "Variables",                "Fundamentals"),
    ("functions",               "Functions",                "Fundamentals"),
    ("control_flow",            "Control Flow",             "Fundamentals"),
    ("recursion",               "Recursion",                "Fundamentals"),

    # ── Object-Oriented Programming ──────────────────────────
    ("oop",                     "Object-Oriented Programming", "OOP"),
    ("classes",                 "Classes",                  "OOP"),
    ("objects",                 "Objects",                  "OOP"),
    ("inheritance",             "Inheritance",              "OOP"),
    ("polymorphism",            "Polymorphism",             "OOP"),
    ("encapsulation",           "Encapsulation",            "OOP"),
    ("abstraction",             "Abstraction",              "OOP"),
    ("methods",                 "Methods",                  "OOP"),
    ("constructors",            "Constructors",             "OOP"),

    # ── Data Structures ──────────────────────────────────────
    ("data_structures",         "Data Structures",          "Data Structures"),
    ("arrays",                  "Arrays",                   "Data Structures"),
    ("linked_lists",            "Linked Lists",             "Data Structures"),
    ("stacks",                  "Stacks",                   "Data Structures"),
    ("queues",                  "Queues",                   "Data Structures"),
    ("trees",                   "Trees",                    "Data Structures"),
    ("graphs",                  "Graphs",                   "Data Structures"),
    ("hash_tables",             "Hash Tables",              "Data Structures"),

    # ── Algorithms ───────────────────────────────────────────
    ("algorithms",              "Algorithms",               "Algorithms"),
    ("sorting",                 "Sorting",                  "Algorithms"),
    ("searching",               "Searching",                "Algorithms"),
    ("dynamic_programming",     "Dynamic Programming",      "Algorithms"),
    ("time_complexity",         "Time Complexity",          "Algorithms"),
    ("space_complexity",        "Space Complexity",         "Algorithms"),

    # ── Systems & Infrastructure ─────────────────────────────
    ("databases",               "Databases",                "Systems"),
    ("sql",                     "SQL",                      "Systems"),
    ("indexing",                "Indexing",                  "Systems"),
    ("apis",                    "APIs",                     "Systems"),
    ("operating_systems",       "Operating Systems",        "Systems"),
    ("memory_management",       "Memory Management",        "Systems"),
    ("concurrency",             "Concurrency",              "Systems"),
    ("networking",              "Networking",               "Systems"),

    # ── Frontend & UI ────────────────────────────────────────
    ("html_css",                "HTML & CSS",               "Frontend"),
    ("javascript_ts",           "JavaScript / TypeScript",  "Frontend"),
    ("react",                   "React / Component Frameworks","Frontend"),
    ("responsive_design",       "Responsive & Accessible Design","Frontend"),
    ("ui_ux",                   "UI / UX Principles",       "Frontend"),

    # ── Dev Practices ────────────────────────────────────────
    ("git",                     "Git",                      "Dev Practices"),
    ("testing",                 "Testing",                  "Dev Practices"),
    ("ci_cd",                   "CI / CD Pipelines",        "Dev Practices"),
    ("docker_containers",       "Docker & Containers",      "Dev Practices"),
    ("cloud_infra",             "Cloud Infrastructure",     "Dev Practices"),

    # ── Product & Collaboration ──────────────────────────────
    ("documentation",           "Documentation",            "Product"),
    ("project_management",      "Project Management",       "Product"),
    ("system_design",           "System Design",            "Product"),

    # ── Hackathon / Applied ──────────────────────────────────
    ("prototyping",             "Rapid Prototyping",        "Hackathon"),
    ("integrations",            "Third-party Integrations", "Hackathon"),
    ("problem_solving",         "Creative Problem Solving", "Hackathon"),
]

# Derived look-ups (computed once at import time)
CATEGORY_KEYS: List[str]      = [c[0] for c in CATEGORIES]
CATEGORY_MAP:  Dict[str, str] = {c[0]: c[1] for c in CATEGORIES}
CATEGORY_GROUPS: Dict[str, str] = {c[0]: c[2] for c in CATEGORIES}

NUM_CATEGORIES: int = len(CATEGORY_KEYS)


def zero_scores() -> Dict[str, float]:
    """Return a dict with every category key set to 0.0."""
    return {k: 0.0 for k in CATEGORY_KEYS}
