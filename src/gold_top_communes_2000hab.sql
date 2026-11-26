-- Gold : classement limité aux communes de 2 000 habitants et plus.
-- Dans les très petites communes, quelques gros sites classés « résidentiel »
-- (résidences secondaires, domaines) faussent la moyenne par habitant.
SELECT annee, code_departement, code_commune, nom_commune, population,
       elec_res_kwh_hab, gaz_res_kwh_hab, energie_res_kwh_hab, evolution_res_pct,
       RANK() OVER (PARTITION BY annee ORDER BY energie_res_kwh_hab DESC) AS rang
FROM gold_hab
WHERE population >= 2000
ORDER BY annee, rang
