# External test data

## Attach this on Kaggle

**Dataset slug:** `aaryapatel98/indian-diabetic-retinopathy-image-dataset`

Folder layout, from Kaggle's file listing (1,488 files, about 1 GB). The outer folder name really contains `%20`:

```text
B.%20Disease%20Grading/
  B. Disease Grading/
    1. Original Images/
      a. Training Set/    413 images, IDRiD_001.jpg to IDRiD_413.jpg
      b. Testing Set/     103 images, IDRiD_001.jpg to IDRiD_103.jpg
    2. Groundtruths/
      a. IDRiD_Disease Grading_Training Labels.csv
      b. IDRiD_Disease Grading_Testing Labels.csv
    CC-BY-4.0.txt
    LICENSE.txt
A.%20Segmentation/        not used
C.%20Localization/        not used
```

Run this on Kaggle. Check the mount path with `ls /kaggle/input` first:

```bash
python ml/prepare_external.py \
  --in_dir /kaggle/input/indian-diabetic-retinopathy-image-dataset \
  --out_dir /kaggle/working/external/idrid
```

Expected output: `Wrote 516 images`, grades `{0: 168, 1: 25, 2: 168, 3: 93, 4: 62}`. The script stops and writes nothing if the counts differ.

Then pass it to `ml/evaluate.py`:

```bash
--ext_csv /kaggle/working/external/idrid/external.csv \
--ext_dir /kaggle/working/external/idrid/images \
--ext_name idrid
```

IDRiD is the only external set. Do not attach `mariaherrerot/idrid-dataset` (see below).

## IDRiD (disease grading subset)

**Licence.** CC BY 4.0, so reuse and redistribution are allowed with attribution. The IEEE DataPort page lists Creative Commons Attribution, and the licence file shipped with the dataset reads: "The IDRiD dataset is licensed under a Creative Commons Attribution 4.0 International License", (c) Prasanna Porwal, Samiksha Pachade and Manesh Kokare.

**Attribution to include** in RESULTS.md and any report: Porwal et al., "Indian Diabetic Retinopathy Image Dataset (IDRiD)", IEEE DataPort, 2018, doi:10.21227/H25W98, and Porwal et al., Data 3(3):25, 2018, doi:10.3390/data3030025.

**Official download.** IEEE DataPort, `B. Disease Grading.zip` (202.57 MB). It needs an IEEE account. The page says both "accessible to all logged in users" and "requires an IEEE DataPort Subscription", so access there is unclear. The Kaggle copy avoids the question.

**Kaggle copy (slug at the top of this file)**

- Licence on Kaggle: CC BY 4.0, which matches the original.
- 1,488 files, about 1 GB. Its folders match the official zips (A. Segmentation, B. Disease Grading, C. Localization), with `LICENSE.txt` and `CC-BY-4.0.txt` in each.
- Grading subset: 413 train and 103 test images, the official split sizes, plus both label CSVs.

**Label scale.** Five grades, 0 to 4, mapped to APTOS 0 to 4 with no change. The class names on the Hugging Face copy are noDR, mildDR, moderateDR, severeDR and proDR.

**Reference grade counts** (Hugging Face `amin-nejad/idrid-disease-grading`, CC BY 4.0):

| Split | 0 | 1 | 2 | 3 | 4 | Total |
|---|---|---|---|---|---|---|
| Train | 134 | 20 | 136 | 74 | 49 | 413 |
| Test | 34 | 5 | 32 | 19 | 13 | 103 |
| All | 168 | 25 | 168 | 93 | 62 | 516 |

**Verified on Kaggle (2026-11-05, kernel `sha547/retinascan-phase2`)**

- `prepare_external.py` found both official label CSVs and their columns, matched every label
  to an image, and the grade counts matched the reference exactly:
  `Wrote 516 images; grades {0: 168, 1: 25, 2: 168, 3: 93, 4: 62}`.
- The check compares counts, not per-image labels. It would catch a wrong label set, but not
  labels swapped between images with the same totals.

**Still not fully confirmed: what grade 4 means**

- The IDRiD data paper (Porwal et al., *Data* 2018) describes the scale as
  "0 (No apparent DR) to 4 (Severe DR)". A later IDRiD benchmark paper states that the grading
  follows the international clinical (ICDR) protocol, in which grade 4 is proliferative DR.
  The challenge paper that would settle the naming could not be retrieved.
- We map IDRiD 0 to 4 onto APTOS 0 to 4 unchanged (ICDR). **Referable-DR results (grade >= 2) do
  not depend on this**, because grades 3 and 4 are referable either way. The 5-class IDRiD
  accuracy and QWK do rest on the ICDR assumption.
- Sources: https://www.doi.org/10.3390/DATA3030025 , https://arxiv.org/pdf/2008.09772 ,
  https://ieee-dataport.org/node/956

**Mismatches with APTOS**

- Both datasets come from India (APTOS from Aravind Eye Hospital), so IDRiD tests a different source and camera setup, not a different population. Report it that way.
- Images are 4288 x 2848 at 50 degree field of view, per the Kaggle listing. Run the same `crop_retina` and resize as training.
- Train and test filenames collide (all 103 test names also exist in train). Output ids carry the split, for example `idrid_test_IDRiD_001`.
- Grade 1 has only 25 images, so any per-class number for it will be noisy.

**Why not `mariaherrerot/idrid-dataset`.** It has 455 images, not 516, and its Kaggle licence is "Unknown". Its grade counts are 129/22/156/84/64. Grade 4 has 64 images against 62 in the reference, so it cannot be a subset of the official labels.

## Messidor-2: skipped

Decided 2026-11-05: Messidor-2 is not used. ADCIS terms prohibit copying and redistribution, so the Kaggle copy `mariaherrerot/messidor2preprocess` is not licence-compatible, and the official images need registration. `prepare_external.py` handles IDRiD only.

## Sources

- IDRiD on IEEE DataPort: https://ieee-dataport.org/open-access/indian-diabetic-retinopathy-image-dataset-idrid
- IDRiD Kaggle mirror: https://www.kaggle.com/datasets/aaryapatel98/indian-diabetic-retinopathy-image-dataset
- IDRiD Hugging Face copy: https://huggingface.co/datasets/amin-nejad/idrid-disease-grading
- Rejected IDRiD copy: https://www.kaggle.com/datasets/mariaherrerot/idrid-dataset
- Messidor-2 at ADCIS: https://www.adcis.net/en/third-party/messidor2/
- APTOS source and scale: https://arxiv.org/pdf/2409.07422
