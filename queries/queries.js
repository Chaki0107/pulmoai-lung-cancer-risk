// Requêtes d'interrogation de la base PulmoAI (collection "patients")
// Utilisation : mongosh "mongodb://localhost:27017" --file queries/queries.js
db = db.getSiblingDB("pulmoai");

// 1. Fumeurs actifs au stade IV, du plus court au plus long suivi
printjson(
  db.patients.find({ "smoking.status": "Current Smoker", "clinical.stage": "Stage IV" })
    .sort({ "outcome.survival_months": 1 })
    .limit(5)
    .toArray()
);

// 2. Taux de survie par stade
printjson(
  db.patients.aggregate([
    { $group: {
        _id: "$clinical.stage",
        total: { $sum: 1 },
        survived: { $sum: { $cond: ["$outcome.survived", 1, 0] } }
    } },
    { $addFields: { survival_rate_pct: { $multiply: [{ $divide: ["$survived", "$total"] }, 100] } } },
    { $sort: { _id: 1 } }
  ]).toArray()
);

// 3. Nombre de fumeurs actifs qui toussent
printjson(
  db.patients.countDocuments({ "smoking.status": "Current Smoker", symptoms: "Coughing" })
);

// 4. Répartition des traitements par stade
printjson(
  db.patients.aggregate([
    { $group: { _id: { stage: "$clinical.stage", treatment: "$outcome.treatment" }, count: { $sum: 1 } } },
    { $sort: { "_id.stage": 1, count: -1 } }
  ]).toArray()
);

// 5. Symptômes les plus fréquents
printjson(
  db.patients.aggregate([
    { $unwind: "$symptoms" },
    { $group: { _id: "$symptoms", patients: { $sum: 1 } } },
    { $sort: { patients: -1 } }
  ]).toArray()
);

// Ajoute ici tes autres requêtes.
