-- Vue mensuelle : saisonnalité annuelle, pour comparer été vs hiver par exemple.

with enriched as (

    select * from {{ ref('int_measurements_enriched') }}

)

select
    measured_month,
    count(*)                                            as nb_measurements,
    avg(wind_avg_kmh)                                    as mean_kmh,
    percentile_cont(0.5) within group (order by wind_avg_kmh) as median_kmh,
    percentile_cont(0.9) within group (order by wind_avg_kmh) as p90_kmh,
    max(wind_gust_kmh)                                   as max_gust_kmh,

    -- % de mesures au-dessus d'un seuil praticable (à ajuster, ex 12 km/h ~ 6.5nds)
    100.0 * sum(case when wind_avg_kmh >= 12 then 1 else 0 end) / count(*) as pct_above_12kmh

from enriched
group by measured_month
order by measured_month
