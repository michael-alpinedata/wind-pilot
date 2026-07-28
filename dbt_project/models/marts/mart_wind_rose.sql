-- Rose des vents : distribution direction x tranche de force.
-- Format pensé pour être consommé directement par une lib de viz
-- (une ligne = un secteur direction / tranche de vitesse, avec le comptage).

with enriched as (

    select * from {{ ref('int_measurements_enriched') }}

),

bucketed as (

    select
        wind_direction_16pt,
        case
            when wind_avg_kmh < 8  then '0-8 km/h'
            when wind_avg_kmh < 15 then '8-15 km/h'
            when wind_avg_kmh < 22 then '15-22 km/h'
            when wind_avg_kmh < 30 then '22-30 km/h'
            else '30+ km/h'
        end as speed_bucket

    from enriched
    where wind_direction_16pt is not null

)

select
    wind_direction_16pt,
    speed_bucket,
    count(*) as nb_measurements

from bucketed
group by wind_direction_16pt, speed_bucket
order by wind_direction_16pt, speed_bucket
