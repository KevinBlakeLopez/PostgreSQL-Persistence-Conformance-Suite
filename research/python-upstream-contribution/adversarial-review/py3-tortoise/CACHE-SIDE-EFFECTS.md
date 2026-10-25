# Automatic pip cache side effects

Observed execution-constraint deviation: the escalated pip installs used pip's default shared cache. The environment installations themselves are in my temporary root, but pip also wrote the following shared-cache entries. This should have been prevented with `PIP_CACHE_DIR=<scratch>/pip-cache` or `--no-cache-dir`. No later installs were needed after detection.

The two self-check records below unambiguously identify my virtualenv paths in their JSON `key` values. They were newly created by this review. They may be deleted together with the review's temporary root:

- `$HOME/Library/Caches/pip/selfcheck/519ee1a44f8e2e6da980718d3706f8baa16be35d4cd8fb77dd76f45b`
- `$HOME/Library/Caches/pip/selfcheck/85d55830fb96ac9652eb8ca0f0329aa6b73f923d288648a60c90091a`

The following HTTP-cache metadata files were modified within the observed install windows (02:04:20–02:04:30 and 02:30:40–02:30:50 UTC). They correspond to metadata refreshes of the cached wheels used by pip. Concurrent sessions prevent exclusive ownership attribution from timing alone. I left these shared entries intact. They are recorded for audit, not as instructions to delete someone else's cache:

- `$HOME/Library/Caches/pip/http-v2/1/9/2/f/9/192f90df60c31a94999870fce0167401b042b5a8bf3f7f2fdecc262d`
- `$HOME/Library/Caches/pip/http-v2/1/9/9/4/f/1994f8e6b2be64a354078558017f199a63a63845ad7898117cea28f5`
- `$HOME/Library/Caches/pip/http-v2/2/8/a/f/c/28afcd56edf76777b7f0ba6af9bc937ce39f1469a94e4eb654feb6b0`
- `$HOME/Library/Caches/pip/http-v2/6/8/0/d/4/680d4dd80dc6a3d2df9b9478dfcc8e81e0e4f130e154a3268b98b877`
- `$HOME/Library/Caches/pip/http-v2/8/2/8/7/7/82877091ff32c0fc98aef299356436de6a9eb733b9a076d6d7063e3a`
- `$HOME/Library/Caches/pip/http-v2/8/8/f/7/d/88f7d71f2d1361f8fb38230bb8ae05bdb624c08a2414e1c535731370`
- `$HOME/Library/Caches/pip/http-v2/8/b/2/4/2/8b24226e2da88df4abeee0d8ca6bce79b19ca2bcd5f94b543939c66c`
- `$HOME/Library/Caches/pip/http-v2/9/1/6/3/2/9163228b7d2afed58cccf392b60beb7f398a703c63500e7e9974551d`
- `$HOME/Library/Caches/pip/http-v2/9/3/9/7/8/93978e7dac5547306a196beedc5a8689fb0cf42b0cc985ddf5bfe8a0`
- `$HOME/Library/Caches/pip/http-v2/9/d/c/c/e/9dccef524c9f359b3a75b6f86f4ab8afaa5e3cd261f31c817fcba734`
- `$HOME/Library/Caches/pip/http-v2/c/0/b/1/8/c0b189c21493ac131f0dd980c301012ccdcdf80d500d85eca570b41c`
- `$HOME/Library/Caches/pip/http-v2/d/0/1/3/0/d01300ab1825acaa64dc951d1f645406277af51131608125f32a3858`
- `$HOME/Library/Caches/pip/http-v2/e/2/0/7/4/e207426cbcf220918fdf354826064190a066f96cd6ad8830f1f11fdc`
- `$HOME/Library/Caches/pip/http-v2/f/0/e/2/8/f0e28ece914c8ef232bd16f2cf5fb25d89ec879e8b2a76672e0df90c`
- `$HOME/Library/Caches/pip/http-v2/f/2/a/2/3/f2a2370e1b94dff837e3d43805ca85317ab1e38b93a46eb9d36c2d94`

Their parent cache directories already existed before this review, and the neighboring wheel-body files predate these installs. No cache wheel body created within these install windows was found. The complete path inventory separately lists the two definitely created self-check files. The review verdict concerns the draft; this execution deviation is reported independently.
