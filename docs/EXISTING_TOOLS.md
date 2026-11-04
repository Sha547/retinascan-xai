# What existing DR screening tools already do (checked 2026-11-05)

Purpose: answer the judge question "Eyenuk, Remidio and others already do DR
screening. What is different?" without over-claiming. Based on a short web
search of published studies and labels; **not** a full product review.

| Tool | Output found in sources | Image-quality handling | Regulatory status (per sources) |
| ---- | ----------------------- | ---------------------- | -------------------------------- |
| EyeArt (Eyenuk) | per eye: referable DR / non-referable DR / ungradable | reports "ungradable"; protocol retakes after dilation | FDA cleared 2020 |
| LumineticsCore (formerly IDx-DR, Digital Diagnostics) | more-than-mild DR detected / not detected / insufficient quality | "insufficient quality" output; label says re-test or refer when there is no result | FDA (US indications for use) |
| Medios AI (Remidio) | referable DR / any DR; runs **offline** on a smartphone fundus camera | flags poor-quality images and prompts a retake | CDSCO approval in India |

## What this means for our claims

- **Do not claim** that the quality gate is new: all three tools handle poor
  images. Ours is a standard component.
- **Do not claim** that other tools lack heatmaps or explanations. The sources
  we found do not mention them, but that is not evidence that they don't exist.
- **Do not claim** offline operation (Remidio already has it; ours needs a server).
- **Defensible framing:** we do not claim to invent DR screening. Our prototype
  explores *verifiability and workflow*:
  1. a **calibrated confidence** with an explicit **"not confident: route to
     doctor"** state on *gradable* images (distinct from image-quality rejection),
     with measured accuracy on graded vs. all cases;
  2. **evidence a doctor can check**: a coarse Grad-CAM map plus three similar
     labelled training images;
  3. a **triage queue** ordered by severity and uncertainty, with accept/override
     logging;
  4. **honest external validation**: we report the drop on IDRiD, including that
     the APTOS-tuned operating point does not transfer (sensitivity 0.924 to 0.724;
     see RESULTS.md).
- **Be explicit about the gap:** the commercial tools have prospective clinical
  validation and regulatory approval. We have a public-dataset prototype.

## Sources

- EyeArt real-world meta-analysis and outputs: https://pmc.ncbi.nlm.nih.gov/articles/PMC9264425 ;
  https://www.nice.org.uk/advice/mib265/chapter/Clinical-and-technical-evidence ;
  https://www.reviewofoptometry.com/news/article/aibased-dr-screening-system-exhibits-high-diagnostic-accuracy-but-low-usage
- LumineticsCore / IDx-DR: https://clinicaltrials.gov/study/NCT02963441 ;
  https://www.digitaldiagnostics.com/products/eye-disease/indications-for-use-us/ ;
  https://www.digitaldiagnostics.com/resources/papers-and-trials/validation-of-automated-screening-for-referable-diabetic-retinopathy-with-the-lumineticscore-formerly-known-as-idx-dr-device-in-the-hoorn-diabetes-care-system/
- Remidio Medios AI (offline): https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7039584/ ;
  https://pubmed.ncbi.nlm.nih.gov/31393538/ ;
  https://cm.healio.com/news/ophthalmology/20241125/qa-ai-software-offers-costeffective-dr-screening-without-internet-access
