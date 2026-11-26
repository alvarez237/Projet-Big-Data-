-- Gold : répartition de la consommation par filière et par grand secteur d'activité
SELECT annee, filiere, code_grand_secteur,
       ROUND(SUM(conso_totale_mwh) / 1000, 2) AS conso_gwh,
       SUM(nb_sites) AS nb_points_livraison,
       ROUND(100 * SUM(conso_totale_mwh)
             / SUM(SUM(conso_totale_mwh)) OVER (PARTITION BY annee, filiere), 1) AS part_pct
FROM conso
GROUP BY annee, filiere, code_grand_secteur
ORDER BY annee, filiere, conso_gwh DESC
