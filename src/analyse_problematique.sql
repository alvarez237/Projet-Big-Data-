-- Requêtes SQL analytiques qui répondent à la problématique.
-- Exécutées par DuckDB sur les tables gold (Parquet sur S3) : python src/run_analyse.py
-- La vue "hab" = gold/conso_par_habitant ; "secteur" = gold/conso_par_secteur.

-- Q1. Quelles communes (>= 2 000 habitants) consomment le plus d'énergie résidentielle
--     par habitant la dernière année ?
SELECT code_departement AS dep, nom_commune, population,
       elec_res_kwh_hab, gaz_res_kwh_hab, energie_res_kwh_hab,
       RANK() OVER (ORDER BY energie_res_kwh_hab DESC) AS rang
FROM hab
WHERE annee = (SELECT MAX(annee) FROM hab) AND population >= 2000
ORDER BY rang
LIMIT 10;

-- Q2. Comment la consommation résidentielle par habitant a-t-elle évolué par département
--     entre la première et la dernière année ?
WITH d AS (
  SELECT code_departement AS dep, annee,
         1000 * SUM(elec_res_mwh) / SUM(population) AS elec_kwh_hab,
         1000 * SUM(gaz_res_mwh)  / SUM(population) AS gaz_kwh_hab
  FROM hab GROUP BY ALL
)
SELECT dep,
       ROUND(MAX(CASE WHEN annee = (SELECT MIN(annee) FROM hab) THEN elec_kwh_hab + gaz_kwh_hab END)) AS energie_debut_kwh_hab,
       ROUND(MAX(CASE WHEN annee = (SELECT MAX(annee) FROM hab) THEN elec_kwh_hab + gaz_kwh_hab END)) AS energie_fin_kwh_hab,
       ROUND(100 * (MAX(CASE WHEN annee = (SELECT MAX(annee) FROM hab) THEN elec_kwh_hab END)
                  / MAX(CASE WHEN annee = (SELECT MIN(annee) FROM hab) THEN elec_kwh_hab END) - 1), 1) AS evol_elec_pct,
       ROUND(100 * (MAX(CASE WHEN annee = (SELECT MAX(annee) FROM hab) THEN gaz_kwh_hab END)
                  / MAX(CASE WHEN annee = (SELECT MIN(annee) FROM hab) THEN gaz_kwh_hab END) - 1), 1) AS evol_gaz_pct,
       ROUND(100 * (MAX(CASE WHEN annee = (SELECT MAX(annee) FROM hab) THEN elec_kwh_hab + gaz_kwh_hab END)
                  / MAX(CASE WHEN annee = (SELECT MIN(annee) FROM hab) THEN elec_kwh_hab + gaz_kwh_hab END) - 1), 1) AS evol_energie_pct
FROM d GROUP BY dep ORDER BY dep;

-- Q3. Quelle part des communes a réduit sa consommation résidentielle par habitant
--     entre la première et la dernière année ?
WITH e AS (
  SELECT code_commune, code_departement AS dep,
         MAX(CASE WHEN annee = (SELECT MIN(annee) FROM hab) THEN energie_res_kwh_hab END) AS debut,
         MAX(CASE WHEN annee = (SELECT MAX(annee) FROM hab) THEN energie_res_kwh_hab END) AS fin
  FROM hab GROUP BY ALL
)
SELECT COALESCE(dep, 'TOTAL') AS dep, COUNT(*) AS communes_comparables,
       CAST(SUM(CASE WHEN fin < debut THEN 1 ELSE 0 END) AS INT) AS communes_en_baisse,
       ROUND(100 * SUM(CASE WHEN fin < debut THEN 1 ELSE 0 END) / COUNT(*), 1) AS part_en_baisse_pct,
       ROUND(MEDIAN(100 * (fin / debut - 1)), 1) AS evolution_mediane_pct
FROM e WHERE debut > 0 AND fin > 0  -- 0 = donnée masquée (secret statistique)
GROUP BY ROLLUP (dep) ORDER BY dep NULLS LAST;

-- Q4. Quelles communes (>= 2 000 habitants) ont le plus baissé ou le plus augmenté ?
WITH e AS (
  SELECT code_commune, nom_commune, code_departement AS dep, MAX(population) AS population,
         MAX(CASE WHEN annee = (SELECT MIN(annee) FROM hab) THEN energie_res_kwh_hab END) AS debut,
         MAX(CASE WHEN annee = (SELECT MAX(annee) FROM hab) THEN energie_res_kwh_hab END) AS fin
  FROM hab GROUP BY ALL
), r AS (
  SELECT *, ROUND(100 * (fin / debut - 1), 1) AS evolution_pct,
         ROW_NUMBER() OVER (ORDER BY fin / debut) AS rg_baisse,
         ROW_NUMBER() OVER (ORDER BY fin / debut DESC) AS rg_hausse
  FROM e WHERE population >= 2000 AND debut > 0 AND fin > 0
)
SELECT CASE WHEN rg_baisse <= 5 THEN 'plus forte baisse' ELSE 'plus forte hausse' END AS groupe,
       dep, nom_commune, population, debut AS kwh_hab_debut, fin AS kwh_hab_fin, evolution_pct
FROM r WHERE rg_baisse <= 5 OR rg_hausse <= 5
ORDER BY groupe, evolution_pct;

-- Q5. Le résidentiel pèse-t-il plus ou moins que l'industrie, par filière et par année ?
SELECT annee, filiere,
       ROUND(SUM(CASE WHEN code_grand_secteur = 'RESIDENTIEL' THEN conso_gwh END), 1) AS residentiel_gwh,
       ROUND(SUM(CASE WHEN code_grand_secteur = 'TERTIAIRE' THEN conso_gwh END), 1)   AS tertiaire_gwh,
       ROUND(SUM(CASE WHEN code_grand_secteur = 'INDUSTRIE' THEN conso_gwh END), 1)   AS industrie_gwh,
       ROUND(SUM(conso_gwh), 1) AS total_gwh
FROM secteur GROUP BY ALL ORDER BY filiere, annee;
