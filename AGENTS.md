# RetinaScan XAI: instructions for Codex and other agents

Diabetic retinopathy screening prototype for a national hackathon. Three lanes
work in parallel; see `PLAN.md`. API shapes are defined in `docs/CONTRACT.md`,
with example (fake) payloads in `docs/fixtures/`.

## Hard rules

1. **Never hardcode or invent model numbers** (accuracy, sensitivity, confidence,
   AUC and so on). Every number shown in the UI comes from an API response or a fixture.
2. **No overclaims.** The app must not imply lesion detection, lesion counting,
   offline mode or clinical validation. Grad-CAM shows "regions that most
   influenced the grade"; it is coarse and not lesion detection.
3. When `model.mock` is true, a visible banner must say:
   "Mock model: outputs are not real predictions."
4. Required disclaimer wording: "Research prototype, not clinically validated.
   Final decision must be made by a qualified ophthalmologist."
5. **Stay in your lane.** The frontend lane edits `web/` only (plus its own
   section of `PROGRESS.md`). Contract problems go under "Contract change
   requests" in `PROGRESS.md`; never edit `docs/CONTRACT.md`.
6. Never commit node_modules, build output, datasets, patient images or secrets.
7. Work on your lane branch; never push to `main`, never force-push.
8. Before finishing: `npm run build` and `npm run lint` pass in `web/`.
