# Unreal gym suite artifacts

SB3 checkpoints and train logs for the primitive gym suite land here:

```text
artifacts/<env_name>/ppo.zip
```

Env names match the plan: `chase_point`, `avoid_hazards`, `collect_coins`.

This directory’s contents (except this README) are gitignored. Create env
subdirs via `gym_common.ensure_artifacts_dir` or `train_ppo`.
