"""
Transformation CSV → JSON pour MongoDB
Dataset : Lung Cancer
Auteur  : généré avec Claude
Usage   : python3 scripts/transform_to_mongodb.py   (depuis la racine du dépôt)
Sortie  : data/lung_cancer_mongodb.json  (prêt pour mongoimport --jsonArray)

Champs supprimés :
  - WHO_Region           (trop générique, Country suffit)
  - Diagnosis_Year       (redondant avec Diagnosis_Date)
  - Diagnosis_Date       (supprimé à la demande)
  - NSCLC_Subtype        (supprimé à la demande)
  - Tumor_Size_cm        (supprimé à la demande)
  - Genetic_Mutation     (supprimé à la demande)
  - Metastasis           (supprimé à la demande)
  - Chronic_Lung_Disease (supprimé à la demande)
"""

import pandas as pd
import json
import os

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

INPUT_FILE  = "data/lung_cancer_sample.csv"   # remplace par le dataset complet si tu l'as
OUTPUT_FILE = "data/lung_cancer_mongodb.json"

# Les 10 champs symptômes (Yes/No) → tableau MongoDB
SYMPTOM_COLS = [
    "Coughing",
    "Shortness_of_Breath",
    "Chest_Pain",
    "Coughing_Blood",
    "Fatigue",
    "Weight_Loss",
    "Wheezing",
    "Recurrent_Infections",
    "Swallowing_Difficulty",
    "Finger_Clubbing",
]


# ─────────────────────────────────────────────
# FONCTIONS UTILITAIRES
# ─────────────────────────────────────────────

def yes_no_to_bool(value: str) -> bool:
    """Convertit 'Yes' / 'No' en booléen Python."""
    return str(value).strip() == "Yes"


def build_symptoms(row) -> list:
    """
    Construit un tableau des symptômes présents uniquement.
    Les underscores sont remplacés par des espaces.
    Ex : ['Coughing', 'Chest Pain', 'Fatigue']
    """
    return [
        col.replace("_", " ")
        for col in SYMPTOM_COLS
        if row[col] == "Yes"
    ]


# ─────────────────────────────────────────────
# TRANSFORMATION PRINCIPALE
# ─────────────────────────────────────────────

def transform_row(row) -> dict:
    """
    Transforme une ligne du CSV en document MongoDB structuré.

    Champs conservés et restructurés :
    ┌─────────────────────────────────────────────────────┐
    │ _id            ← Patient_ID                         │
    │ age, gender                                         │
    │ location       ← country seulement                  │
    │ smoking        ← status, cigarettes_per_day,        │
    │                   years_smoking                     │
    │ lifestyle      ← bmi, alcohol_use,                  │
    │                   exercise_frequency                │
    │ risk_factors   ← secondhand_smoke, family_history,  │
    │                   occupational_hazard,              │
    │                   air_pollution_exposure,           │
    │                   asbestos_exposure, radon_exposure │
    │ symptoms       ← tableau des symptômes présents     │
    │ clinical       ← stage, previous_cancer_history,    │
    │                   diagnosis_method                  │
    │ outcome        ← treatment, survival_months,        │
    │                   survived                          │
    └─────────────────────────────────────────────────────┘
    """

    return {
        # ── Identité ──────────────────────────────
        "_id":    row["Patient_ID"],
        "age":    int(row["Age"]),
        "gender": row["Gender"],

        # ── Localisation ──────────────────────────
        # WHO_Region supprimé — Country suffit
        "location": {
            "country": row["Country"],
        },

        # ── Tabagisme ─────────────────────────────
        "smoking": {
            "status":             row["Smoking_Status"],
            "cigarettes_per_day": int(row["Cigarettes_Per_Day"]),
            "years_smoking":      int(row["Years_Smoking"]),
        },

        # ── Mode de vie ───────────────────────────
        "lifestyle": {
            "bmi":                float(row["BMI"]),
            "alcohol_use":        row["Alcohol_Use"],
            "exercise_frequency": row["Exercise_Frequency"],
        },

        # ── Facteurs de risque ────────────────────
        "risk_factors": {
            "secondhand_smoke":       yes_no_to_bool(row["Secondhand_Smoke"]),
            "family_history":         yes_no_to_bool(row["Family_History"]),
            "occupational_hazard":    yes_no_to_bool(row["Occupational_Hazard"]),
            "air_pollution_exposure": row["Air_Pollution_Exposure"],  # Low/Moderate/High
            "asbestos_exposure":      yes_no_to_bool(row["Asbestos_Exposure"]),
            "radon_exposure":         yes_no_to_bool(row["Radon_Exposure"]),
        },

        # ── Symptômes (tableau des présents seulement) ──
        "symptoms": build_symptoms(row),

        # ── Données cliniques ─────────────────────
        # Supprimés : nsclc_subtype, tumor_size_cm, genetic_mutation,
        #             metastasis, chronic_lung_disease
        "clinical": {
            "stage":                   row["Cancer_Stage"],
            "previous_cancer_history": yes_no_to_bool(row["Previous_Cancer_History"]),
            "diagnosis_method":        row["Diagnosis_Method"],
        },

        # ── Résultat ──────────────────────────────
        "outcome": {
            "treatment":       row["Treatment"],
            "survival_months": int(row["Survival_Months"]),
            "survived":        yes_no_to_bool(row["Survived"]),
        },
    }


# ─────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────

def validate(documents: list, expected: int) -> None:
    """Vérifie l'intégrité du résultat avant écriture."""
    ids = [d["_id"] for d in documents]

    assert len(documents) == expected, f"Nombre de documents incorrect : {len(documents)}"
    assert len(set(ids)) == len(ids), "Des _id en doublon ont été détectés !"

    for doc in documents:
        assert isinstance(doc["symptoms"], list),                          "symptômes : liste attendue"
        assert isinstance(doc["risk_factors"]["secondhand_smoke"], bool),  "booléen attendu"
        assert isinstance(doc["outcome"]["survived"], bool),               "booléen attendu"
        # Vérifier que les champs supprimés sont absents
        assert "who_region"            not in doc.get("location", {}), "WHO_Region non supprimé"
        assert "diagnosis_date"        not in doc,                     "Diagnosis_Date non supprimé"
        assert "nsclc_subtype"         not in doc.get("clinical", {}), "NSCLC_Subtype non supprimé"
        assert "tumor_size_cm"         not in doc.get("clinical", {}), "Tumor_Size_cm non supprimé"
        assert "genetic_mutation"      not in doc.get("clinical", {}), "Genetic_Mutation non supprimé"
        assert "metastasis"            not in doc.get("clinical", {}), "Metastasis non supprimé"
        assert "chronic_lung_disease"  not in doc.get("clinical", {}), "Chronic_Lung_Disease non supprimé"

    avg_sym = sum(len(d["symptoms"]) for d in documents) / len(documents)

    print(f"  ✓ {len(documents)} documents valides")
    print(f"  ✓ {len(set(ids))} _id uniques")
    print(f"  ✓ Moyenne symptômes / patient : {avg_sym:.1f}")
    print(f"  ✓ Tous les champs supprimés sont absents")


# ─────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────

def main():
    print(f"\n{'='*52}")
    print("  Transformation CSV → JSON MongoDB")
    print(f"{'='*52}\n")

    # 1. Lecture
    print(f"[1/4] Lecture : {INPUT_FILE}")
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(f"Fichier introuvable : {INPUT_FILE}")
    df = pd.read_csv(INPUT_FILE)
    print(f"  ✓ {df.shape[0]} lignes × {df.shape[1]} colonnes chargées")

    # 2. Transformation
    print("\n[2/4] Transformation des lignes...")
    documents = [transform_row(row) for _, row in df.iterrows()]
    print(f"  ✓ {len(documents)} documents construits")

    # 3. Validation
    print("\n[3/4] Validation...")
    validate(documents, expected=len(df))

    # 4. Écriture JSON
    print(f"\n[4/4] Écriture : {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)
    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"  ✓ Fichier généré ({size_kb:.1f} KB)\n")

    print(f"{'='*52}")
    print("  Import MongoDB :")
    print(f"  mongoimport --db pulmoai --collection patients \\")
    print(f"    --file {OUTPUT_FILE} --jsonArray")
    print(f"{'='*52}\n")


if __name__ == "__main__":
    main()
