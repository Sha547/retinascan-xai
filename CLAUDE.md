# RetinaScan XAI: rules for every agent session

Diabetic retinopathy screening prototype for a national hackathon (Open Innovation).
Read `PLAN.md` for who owns what, `docs/CONTRACT.md` for API and artifact shapes,
and `PROGRESS.md` for current status.

## Hard rules

1. **Never invent or estimate metrics.** Every reported number comes from
   `artifacts/results.json` (or files the evaluation code writes next to it).
   If a number is not in a file, it is not reported.
2. **The test split is never used for tuning.** Temperature, the referable
   threshold, the abstention threshold and the quality thresholds are fitted on
   validation (or train, for quality) only. The test split is scored once.
3. **The similar-case index contains training-split images only.**
4. **No overclaims.** Lesion detection/segmentation, offline mode, regional
   languages, progression tracking and clinical validation are future work, never
   described as built. Grad-CAM is "regions that influenced the grade", not lesion
   detection. Public datasets are not real PHC images.
5. **Stay in your lane.** Edit only the paths your lane owns (see `PLAN.md`).
   Request contract changes under "Contract change requests" in `PROGRESS.md`.
6. **Stop when the user is needed** (logins, licence click-through, sudo, a
   decision). Write exact steps. Do not work around it.
7. **Log progress** in your lane's section of `PROGRESS.md`: done, running, failed, blocked.
8. Never commit datasets, patient images, model weights, `kaggle.json` or the database.
9. Never push to `main` from a lane branch; never force-push. The user merges.
10. Treat downloaded archives as untrusted: extract into a new empty directory and
    never execute anything from them.
