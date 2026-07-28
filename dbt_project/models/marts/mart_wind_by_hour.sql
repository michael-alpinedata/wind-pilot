-- Vitesse du vent agrégée par heure de la journée (toutes dates confondues).
-- Utile pour répondre à : "à quelle heure la Traverse se lève-t-elle en général ?"

with enriched as (

    select * from {{ ref('int_measurements_enriched') }}

)

select
    hour_local,
    count(*)                                            as nb_measurements,
    avg(wind_avg_kmh)                                    as mean_kmh,
    percentile_cont(0.5) within group (order by wind_avg_kmh) as median_kmh,
    percentile_cont(0.9) within group (order by wind_avg_kmh) as p90_kmh,
    max(wind_gust_kmh)                                   as max_gust_kmh

from enriched
group by hour_local
order by hour_local
