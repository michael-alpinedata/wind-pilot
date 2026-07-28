-- Série temporelle journalière : une ligne par jour, avec le comportement
-- jour/nuit dissocié pour visualiser la Traverse au fil des saisons.

with enriched as (

    select * from {{ ref('int_measurements_enriched') }}

)

select
    measured_date_local,
    day_night_slot,
    count(*)                                            as nb_measurements,
    avg(wind_avg_kmh)                                    as mean_kmh,
    percentile_cont(0.5) within group (order by wind_avg_kmh) as median_kmh,
    percentile_cont(0.9) within group (order by wind_avg_kmh) as p90_kmh,
    max(wind_gust_kmh)                                   as max_gust_kmh

from enriched
group by measured_date_local, day_night_slot
order by measured_date_local, day_night_slot
