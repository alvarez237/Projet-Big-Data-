-- Gold : consommation d'électricité et de gaz par commune et par habitant.
-- Le classement se fait sur le résidentiel (catégorie RES) : la consommation des
-- ménages se compare d'une commune à l'autre, ce qui n'est pas le cas de l'industrie.
WITH c AS (
  SELECT annee, code_commune, nom_commune, code_departement,
         SUM(CASE WHEN upper(filiere) LIKE 'ELEC%' AND code_categorie_consommation = 'RES'
                  THEN conso_totale_mwh ELSE 0 END) AS elec_res_mwh,
         SUM(CASE WHEN upper(filiere) LIKE 'GAZ%' AND code_categorie_consommation = 'RES'
                  THEN conso_totale_mwh ELSE 0 END) AS gaz_res_mwh,
         SUM(CASE WHEN upper(filiere) LIKE 'ELEC%' THEN conso_totale_mwh ELSE 0 END) AS elec_totale_mwh,
         SUM(CASE WHEN upper(filiere) LIKE 'GAZ%' THEN conso_totale_mwh ELSE 0 END) AS gaz_totale_mwh
  FROM conso
  GROUP BY annee, code_commune, nom_commune, code_departement
), h AS (
  SELECT c.*, p.population,
         ROUND(1000 * elec_res_mwh / p.population)                  AS elec_res_kwh_hab,
         ROUND(1000 * gaz_res_mwh / p.population)                   AS gaz_res_kwh_hab,
         ROUND(1000 * (elec_res_mwh + gaz_res_mwh) / p.population)  AS energie_res_kwh_hab,
         ROUND(1000 * (elec_totale_mwh + gaz_totale_mwh) / p.population) AS energie_totale_kwh_hab
  FROM c JOIN population p ON c.code_commune = p.code_commune
)
SELECT annee, code_departement, code_commune, nom_commune, population,
       ROUND(elec_res_mwh, 1) AS elec_res_mwh, ROUND(gaz_res_mwh, 1) AS gaz_res_mwh,
       ROUND(elec_totale_mwh, 1) AS elec_totale_mwh, ROUND(gaz_totale_mwh, 1) AS gaz_totale_mwh,
       elec_res_kwh_hab, gaz_res_kwh_hab, energie_res_kwh_hab, energie_totale_kwh_hab,
       ROUND(100 * (energie_res_kwh_hab
             / LAG(energie_res_kwh_hab) OVER (PARTITION BY code_commune ORDER BY annee) - 1), 1)
             AS evolution_res_pct,
       RANK() OVER (PARTITION BY annee ORDER BY energie_res_kwh_hab DESC) AS rang
FROM h
ORDER BY annee, rang
