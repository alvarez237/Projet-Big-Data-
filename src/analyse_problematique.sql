-- Requêtes SQL analytiques qui répondent à la problématique (DuckDB sur les tables gold S3).
-- Vues : hab = gold/conso_par_habitant ; secteur = gold/conso_par_secteur ; synthese = gold/synthese_departement
-- Exécution : python src/run_analyse.py   (ou une par une dans : python src/sql_shell.py)

-- Q1. Quelles communes de 2 000 habitants et plus consomment le plus d'énergie résidentielle par habitant en 2024 ?
SELECT nom_commune, code_departement, population,
       elec_res_kwh_hab, gaz_res_kwh_hab, energie_res_kwh_hab
FROM hab
WHERE annee = 2024 AND population >= 2000
ORDER BY energie_res_kwh_hab DESC
LIMIT 10;

-- Q2. Comment la consommation résidentielle par habitant a-t-elle évolué entre 2022 et 2024, par département ?
SELECT code_departement,
       MAX(CASE WHEN annee = 2022 THEN energie_res_kwh_hab END) AS kwh_hab_2022,
       MAX(CASE WHEN annee = 2023 THEN energie_res_kwh_hab END) AS kwh_hab_2023,
       MAX(CASE WHEN annee = 2024 THEN energie_res_kwh_hab END) AS kwh_hab_2024,
       ROUND(100 * (MAX(CASE WHEN annee = 2024 THEN energie_res_kwh_hab END)
                  / MAX(CASE WHEN annee = 2022 THEN energie_res_kwh_hab END) - 1), 1) AS evolution_2022_2024_pct
FROM synthese
GROUP BY code_departement
ORDER BY code_departement;

-- Q3. Quelle part des communes a réduit sa consommation résidentielle par habitant entre 2022 et 2024 ?
WITH e AS (
  SELECT code_commune, code_departement,
         MAX(CASE WHEN annee = 2022 THEN energie_res_kwh_hab END) AS kwh_2022,
         MAX(CASE WHEN annee = 2024 THEN energie_res_kwh_hab END) AS kwh_2024
  FROM hab
  GROUP BY code_commune, code_departement
)
SELECT COALESCE(code_departement, 'TOTAL') AS departement,
       COUNT(*) AS communes,
       SUM(CASE WHEN kwh_2024 < kwh_2022 THEN 1 ELSE 0 END) AS communes_en_baisse,
       ROUND(100.0 * SUM(CASE WHEN kwh_2024 < kwh_2022 THEN 1 ELSE 0 END) / COUNT(*), 1) AS part_en_baisse_pct,
       ROUND(MEDIAN(100 * (kwh_2024 / kwh_2022 - 1)), 1) AS evolution_mediane_pct
FROM e
WHERE kwh_2022 > 0 AND kwh_2024 > 0
GROUP BY ROLLUP (code_departement)
ORDER BY departement;

-- Q4. Parmi les communes de 2 000 habitants et plus, lesquelles ont le plus baissé et le plus augmenté entre 2022 et 2024 ?
WITH e AS (
  SELECT nom_commune, code_departement, MAX(population) AS population,
         MAX(CASE WHEN annee = 2022 THEN energie_res_kwh_hab END) AS kwh_2022,
         MAX(CASE WHEN annee = 2024 THEN energie_res_kwh_hab END) AS kwh_2024
  FROM hab
  GROUP BY nom_commune, code_departement
), r AS (
  SELECT *, ROUND(100 * (kwh_2024 / kwh_2022 - 1), 1) AS evolution_pct,
         ROW_NUMBER() OVER (ORDER BY kwh_2024 / kwh_2022) AS rang_baisse,
         ROW_NUMBER() OVER (ORDER BY kwh_2024 / kwh_2022 DESC) AS rang_hausse
  FROM e
  WHERE population >= 2000 AND kwh_2022 > 0 AND kwh_2024 > 0
)
SELECT CASE WHEN rang_baisse <= 5 THEN 'plus forte baisse' ELSE 'plus forte hausse' END AS groupe,
       nom_commune, code_departement, population, kwh_2022, kwh_2024, evolution_pct
FROM r
WHERE rang_baisse <= 5 OR rang_hausse <= 5
ORDER BY evolution_pct;

-- Q5. Le résidentiel pèse-t-il plus que le tertiaire et l'industrie, pour l'électricité et pour le gaz ?
SELECT annee, filiere,
       ROUND(SUM(CASE WHEN code_grand_secteur = 'RESIDENTIEL' THEN conso_gwh END), 1) AS residentiel_gwh,
       ROUND(SUM(CASE WHEN code_grand_secteur = 'TERTIAIRE' THEN conso_gwh END), 1) AS tertiaire_gwh,
       ROUND(SUM(CASE WHEN code_grand_secteur = 'INDUSTRIE' THEN conso_gwh END), 1) AS industrie_gwh,
       ROUND(SUM(conso_gwh), 1) AS total_gwh,
       ROUND(100 * SUM(CASE WHEN code_grand_secteur = 'RESIDENTIEL' THEN conso_gwh END) / SUM(conso_gwh), 1) AS part_residentiel_pct
FROM secteur
GROUP BY annee, filiere
ORDER BY filiere, annee;
