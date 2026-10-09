"""
╔══════════════════════════════════════════════════════╗
║   PulmoAI — MongoDB Setup Script                     ║
║   Dataset : lung_cancer_mongodb.json                 ║
║   Usage   : python3 scripts/mongodb_setup.py         ║
╚══════════════════════════════════════════════════════╝

Prérequis :
  pip install pymongo --break-system-packages
  MongoDB en cours d'exécution sur localhost:27017
  (ou modifier MONGO_URI ci-dessous)
"""

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import BulkWriteError, CollectionInvalid
import json, os, sys

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
MONGO_URI   = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
DB_NAME     = "pulmoai"
COLLECTION  = "patients"
JSON_FILE   = "data/lung_cancer_mongodb.json"


def connect():
    print(f"[1/5] Connexion à MongoDB ({MONGO_URI})...")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.server_info()          # lève une exception si non joignable
    db = client[DB_NAME]
    print(f"  ✓ Connecté — base : {DB_NAME}")
    return client, db


def reset_collection(db):
    print(f"\n[2/5] Réinitialisation de la collection '{COLLECTION}'...")
    if COLLECTION in db.list_collection_names():
        db[COLLECTION].drop()
        print(f"  ✓ Ancienne collection supprimée")
    else:
        print(f"  ✓ Aucune collection existante")


def load_and_insert(db):
    print(f"\n[3/5] Chargement de {JSON_FILE}...")
    if not os.path.exists(JSON_FILE):
        raise FileNotFoundError(f"Fichier introuvable : {JSON_FILE}")

    with open(JSON_FILE, "r", encoding="utf-8") as f:
        documents = json.load(f)
    print(f"  ✓ {len(documents)} documents chargés")

    print(f"  → Insertion en base...")
    try:
        result = db[COLLECTION].insert_many(documents, ordered=False)
        print(f"  ✓ {len(result.inserted_ids)} documents insérés")
    except BulkWriteError as e:
        print(f"  ⚠ Insertion partielle : {e.details['nInserted']} insérés, {len(e.details['writeErrors'])} erreurs")


def create_indexes(db):
    print(f"\n[4/5] Création des index...")
    col = db[COLLECTION]

    indexes = [
        # Requêtes fréquentes par stade et survie
        ([("clinical.stage", ASCENDING)],             "idx_stage"),
        ([("outcome.survived", ASCENDING)],           "idx_survived"),
        # Filtres sur les facteurs de risque
        ([("smoking.status", ASCENDING)],             "idx_smoking"),
        ([("risk_factors.family_history", ASCENDING)], "idx_family_history"),
        # Données démographiques
        ([("location.country", ASCENDING)],           "idx_country"),
        ([("age", ASCENDING)],                        "idx_age"),
        ([("gender", ASCENDING)],                     "idx_gender"),
        # Symptômes — multikey index (tableau)
        ([("symptoms", ASCENDING)],                   "idx_symptoms"),
        # Traitement et suivi
        ([("outcome.treatment", ASCENDING)],          "idx_treatment"),
        ([("outcome.survival_months", DESCENDING)],   "idx_survival_months"),
        # Index composé : analyse croisée stade + pays
        ([("clinical.stage", ASCENDING),
          ("location.country", ASCENDING)],           "idx_stage_country"),
    ]

    for index_keys, name in indexes:
        col.create_index(index_keys, name=name)
        fields = ", ".join(f"{k} ({'+' if v == 1 else '-'})" for k, v in index_keys)
        print(f"  ✓ {name:30s} → {fields}")


def validate(db):
    print(f"\n[5/5] Validation...")
    col = db[COLLECTION]
    total = col.count_documents({})
    print(f"  ✓ Total documents   : {total}")

    # Répartition par stade
    pipeline = [
        {"$group": {"_id": "$clinical.stage", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    print(f"  ✓ Répartition par stade :")
    for r in col.aggregate(pipeline):
        print(f"       {r['_id']:12s} → {r['count']} patients")

    # Taux de survie global
    survived = col.count_documents({"outcome.survived": True})
    print(f"  ✓ Taux de survie    : {survived/total*100:.1f}%")

    # Index créés
    idx_list = list(col.index_information().keys())
    print(f"  ✓ Index actifs      : {len(idx_list)} ({', '.join(idx_list[:4])}...)")


def print_sample_queries():
    print(f"""
{'='*56}
  Exemples de requêtes utiles
{'='*56}

# Fumeurs actifs au stade IV
db.patients.find({{"smoking.status": "Current Smoker", "clinical.stage": "Stage IV"}})
           .sort({{"outcome.survival_months": 1}})

# Taux de survie par stade
db.patients.aggregate([
  {{"$group": {{
    "_id": "$clinical.stage",
    "total": {{"$sum": 1}},
    "survived": {{"$sum": {{"$cond": ["$outcome.survived", 1, 0]}}}}
  }}}},
  {{"$addFields": {{
    "survival_rate_pct": {{"$multiply": [
      {{"$divide": ["$survived", "$total"]}}, 100
    ]}}
  }}}}
])

# Patients fumeurs avec symptôme de toux
db.patients.find({{
  "smoking.status": "Current Smoker",
  "symptoms": "Coughing"
}})

# Distribution des traitements par stade
db.patients.aggregate([
  {{"$group": {{
    "_id": {{
      "stage": "$clinical.stage",
      "treatment": "$outcome.treatment"
    }},
    "count": {{"$sum": 1}}
  }}}},
  {{"$sort": {{"_id.stage": 1, "count": -1}}}}
])
""")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print(f"\n{'='*56}")
    print("  PulmoAI — MongoDB Setup")
    print(f"{'='*56}")

    try:
        client, db = connect()
        reset_collection(db)
        load_and_insert(db)
        create_indexes(db)
        validate(db)
        print_sample_queries()
        print(f"{'='*56}")
        print("  Setup terminé avec succès !")
        print(f"  Base     : {DB_NAME}")
        print(f"  Collection: {COLLECTION}")
        print(f"{'='*56}\n")
        client.close()

    except Exception as e:
        print(f"\n  ✗ Erreur : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
