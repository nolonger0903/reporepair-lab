"""How many usable instances are there per repo after filtering?"""

from collections import Counter

from reporepair.tasks import select, swebench

pool = swebench.load_jsonl("data/raw/swebench_lite/test.jsonl")
pool = select.filter_pool(pool, repos=swebench.PYTEST_REPOS)
before = len(pool)
pool = [i for i in pool if not swebench.has_unselectable_ids(i)]
print(f"filtered: {before} -> usable pool: {len(pool)}")
for repo, count in sorted(Counter(i["repo"] for i in pool).items(), key=lambda x: -x[1]):
    print(f"  {repo:<32} {count}")
