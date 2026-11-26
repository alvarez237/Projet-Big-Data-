-- Gold : synthèse par département et par année (réponse à la problématique).
-- Consommation résidentielle par habitant du département (pondérée par la population),
-- évolution par rapport à l'année précédente et part des communes en baisse.
WITH d AS (
  SELECT annee, code_departement,
         COUNT(*)                                        AS nb_communes,
         SUM(population)                                 AS population,
         SUM(elec_res_mwh)                               AS elec_res_mwh,
         SUM(gaz_res_mwh)                                AS gaz_res_mwh,
         SUM(CASE WHEN evolution_res_pct < 0 THEN 1 ELSE 0 END) AS nb_communes_en_baisse,
         SUM(CASE WHEN evolution_res_pct IS NOT NULL THEN 1 ELSE 0 END) AS nb_communes_comparables,
         PERCENTILE_APPROX(energie_res_kwh_hab, 0.5)     AS mediane_res_kwh_hab
  FROM gold_hab
  GROUP BY annee, code_departement
)
SELECT annee, code_departement, nb_communes, population,
       ROUND(1000 * elec_res_mwh / population)                 AS elec_res_kwh_hab,
       ROUND(1000 * gaz_res_mwh / population)                  AS gaz_res_kwh_hab,
       ROUND(1000 * (elec_res_mwh + gaz_res_mwh) / population) AS energie_res_kwh_hab,
       mediane_res_kwh_hab,
       ROUND(100 * ((elec_res_mwh + gaz_res_mwh)
             / LAG(elec_res_mwh + gaz_res_mwh) OVER (PARTITION BY code_departement ORDER BY annee) - 1), 1)
             AS evolution_res_pct,
       CASE WHEN nb_communes_comparables > 0
            THEN ROUND(100 * nb_communes_en_baisse / nb_communes_comparables, 1) END AS part_communes_en_baisse_pct
FROM d
ORDER BY code_departement, annee
