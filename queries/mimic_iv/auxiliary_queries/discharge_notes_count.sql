WITH discharge_notes AS (  
  SELECT
    'Discharge Notes' AS dsc_source,
    count(*) AS mtr_count
  FROM
    `physionet-data.mimiciv_note.discharge`
),

discharge_notes_with_patient_info AS (
  SELECT
    'Discharge Notes AND Patient Info' AS dsc_source,
    count(*) AS mtr_count
  FROM
    `physionet-data.mimiciv_note.discharge` n
  INNER JOIN
    `physionet-data.mimiciv_3_1_hosp.patients` p
      ON n.subject_id = p.subject_id
)

SELECT *
FROM discharge_notes

UNION ALL

SELECT *
FROM discharge_notes_with_patient_info
