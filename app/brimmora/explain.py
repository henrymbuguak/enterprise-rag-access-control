"""Shows how BM25, vector, hybrid, and reranked results differ for one user and question."""
import sys

from . import identity, search


def show(label, hits, score_key):
    print(f"{label}")
    for i, h in enumerate(hits[:5], 1):
        print(f"  {i}. {h['document_id']:42} {score_key}={h[score_key]:.3f}")
    if not hits:
        print("  (no results)")
    print()


def main():
    user, question = sys.argv[1], sys.argv[2]
    groups = identity.groups_for(user)
    print(f"user={user}  groups={groups}\nquestion={question!r}\n")
    for mode in ("bm25", "vector", "hybrid"):
        show(mode.upper(), search.search(question, groups, k=10, mode=mode), "score")
    show("HYBRID + RERANK", search.rerank(question, search.search(question, groups)), "rerank_score")


if __name__ == "__main__":
    main()
