-- discharge_notes.sql
-- MIMIC-IV discharge summaries: fetch only the columns we need.

-- WITH final AS (
  SELECT
      n.note_id,
      n.subject_id,
      n.hadm_id,
      n.text,

      -- Clinical stratification variable (ICU exposure during the admission)
      CASE
          WHEN i.hadm_id IS NOT NULL THEN 'ICU'
          ELSE 'Non-ICU'
      END AS unit_type,

      -- Demographic stratification variable
      p.gender AS patient_gender,

      -- 1. Patient Age on Admission
      SAFE_CAST(FLOOR(
          (DATETIME_DIFF(ad.admittime, DATETIME(p.anchor_year, 1, 1, 0, 0, 0), DAY) / 365.25) + p.anchor_age
      ) AS INT64) AS patient_age_on_admission,
          
      -- 2. Patient Age on Discharge Note
      SAFE_CAST(FLOOR(
          (DATETIME_DIFF(n.charttime, DATETIME(p.anchor_year, 1, 1, 0, 0, 0), DAY) / 365.25) + p.anchor_age
      ) AS INT64) AS patient_age_on_discharge_note

  FROM
      `physionet-data.mimiciv_note.discharge` n

  LEFT JOIN
      `physionet-data.mimiciv_3_1_hosp.patients` p
      ON n.subject_id = p.subject_id

  LEFT JOIN
      `physionet-data.mimiciv_3_1_hosp.admissions` ad
      ON ad.subject_id = p.subject_id AND ad.hadm_id = n.hadm_id

  LEFT JOIN (
      -- DISTINCT avoids row multiplication when an admission has
      -- multiple ICU stays (transfers, readmissions to ICU, etc.)
      SELECT DISTINCT hadm_id
      FROM `physionet-data.mimiciv_3_1_icu.icustays`
  ) i 
  ON n.hadm_id = i.hadm_id

/*
 PASSAR ESTA PARTE DE BAIXO PARA O PYTHON
)

SELECT 
    *,
    CASE 
        WHEN patient_age_on_admission BETWEEN 0 AND 4   THEN '[0-4]'
        WHEN patient_age_on_admission BETWEEN 5 AND 9   THEN '[5-9]'
        WHEN patient_age_on_admission BETWEEN 10 AND 19 THEN '[10-19]'
        WHEN patient_age_on_admission BETWEEN 20 AND 24 THEN '[20-24]'
        WHEN patient_age_on_admission BETWEEN 25 AND 59 THEN '[25-59]'
        WHEN patient_age_on_admission >= 60             THEN '[60+]'
        ELSE '[Unknown]'
    END AS age_group_on_admission,

    CASE 
        WHEN patient_age_on_discharge_note BETWEEN 0 AND 4   THEN '[0-4]'
        WHEN patient_age_on_discharge_note BETWEEN 5 AND 9   THEN '[5-9]'
        WHEN patient_age_on_discharge_note BETWEEN 10 AND 19 THEN '[10-19]'
        WHEN patient_age_on_discharge_note BETWEEN 20 AND 24 THEN '[20-24]'
        WHEN patient_age_on_discharge_note BETWEEN 25 AND 59 THEN '[25-59]'
        WHEN patient_age_on_discharge_note >= 60             THEN '[60+]'
        ELSE '[Unknown]'

    END AS age_group_on_discharge_note
FROM final

ESTRATIFICAÇÃO / REPRESENTATIVIDADE:
    - Comprimento notas das medicações de admissão e alta;
    - ICU / NON-ICU;
    - Age Group;
    - Gender;

Granularidade: 
    - discharge notes
    - remover notas com pacientes a null;
    - remover notas de medicação a null para admissão e depois na alta;

*/