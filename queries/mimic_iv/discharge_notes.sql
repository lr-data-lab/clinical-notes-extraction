-- MIMIC-IV discharge notes: fetch only the required columns

SELECT
    n.note_id,
    n.subject_id,
    n.hadm_id,
    n.text

FROM
    `physionet-data.mimiciv_note.discharge` n
