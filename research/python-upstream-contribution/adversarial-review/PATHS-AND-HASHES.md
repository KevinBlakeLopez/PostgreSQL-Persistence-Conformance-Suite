# Paths and hashes in this record

Written by: Claude Opus 5.5 (low), 2026-10-25. The review itself is by GPT-6 / Codex (see `REVIEW.md`).

Local absolute paths were replaced before this directory was committed. `$WORKTREE` is the PPCS checkout the review ran against, and `$HOME` is the home directory. Paths under `/private/tmp/` are the reviewer's temporary directories and were left as recorded. Apart from the hash updates below, nothing else in any file changed.

The replacement changed the content of the files below, so every SHA-256 recorded for them was updated: in `py3-tortoise/evidence/SHA256SUMS.txt`, `py3-tortoise/FRESH-RUN.md` and `py3-tortoise/evidence/install-check.txt`. `shasum -a 256 -c SHA256SUMS.txt` in `py3-tortoise/evidence/` passes for all 52 entries. The original hashes are listed so that the files as first recorded can still be checked against them.

| File | SHA-256 as recorded | SHA-256 after the replacement |
| --- | --- | --- |
| `py3-tortoise/evidence/install-check.txt` | `3f7020cde6cdf1e994b9f68248d977cde241c24d083b166df93e3318855770a6` | `4b2e0dbed8e6de8ba7ec2e9618e32faeb7c3ee02e057f08ddbc6a7311e3e05ff` |
| `py3-tortoise/evidence/integrity.py` | `9ebcb0db5096372921904e48ab808a5a039841a9e7f33590f0f178992c5fc4d4` | `3e12d77826fde6b27b527fc9991224c891fdb477ce8b2eef5da0a4940aaafba8` |
| `py3-tortoise/evidence/outputs/install-asyncpg-run-psycopg.out` | `cdb9a764c35545feb0b1f104dbb4a5edc3be5666844dbdd6d2f51b92345583e9` | `0e7c73c190dd765b060cdac9f2a41d528afa8e8bf5b153299ff97a5315de946e` |
| `py3-tortoise/evidence/outputs/install-psycopg-run-asyncpg.out` | `a0d7b30aefd36baa4cb9b4997c3e706e0edee550607cd7f4a7e53ed1e270cf4d` | `3abe7be866956883e2db9d2a911d41df0624f1a6402a9b492211a00a7329d48f` |
| `py3-tortoise/evidence/outputs/install-psycopg-run-psycopg.out` | `a0d7b30aefd36baa4cb9b4997c3e706e0edee550607cd7f4a7e53ed1e270cf4d` | `3abe7be866956883e2db9d2a911d41df0624f1a6402a9b492211a00a7329d48f` |
| `py3-tortoise/evidence/recorded_check.py` | `fe4e7a3dd6a27826ba78c0f39982231e8c4f7fd38cd4cbede07a72368da90768` | `99b7317d8a264a657a6d9d2cb07128b5b86d410419cf96f3bbfd3a5f19fe1863` |
| `py3-tortoise/evidence/run.py` | `02ad7665fe6600470d77aab874050c3004307e28612571afca7d6aab6a3dc454` | `2eb83f5e6f56f5417dce26837ea7baccae933af620b34ca045fc943a860b1012` |
