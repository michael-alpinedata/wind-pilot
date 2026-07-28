with staged as (

    select * from {{ ref('stg_pioupiou_measurements') }}

),

enriched as (

    select
        *,
        date_trunc('hour', measured_at)            as measured_hour,
        (measured_at at time zone 'Europe/Paris')::date as measured_date_local,
        extract(hour from measured_at at time zone 'Europe/Paris')::int as hour_local,
        to_char(measured_at, 'YYYY-MM')            as measured_month,

        -- créneau horaire indicatif pour isoler la fenêtre de Traverse
        case
            when extract(hour from measured_at at time zone 'Europe/Paris') between 10 and 19
                then 'jour'
            else 'nuit'
        end                                          as day_night_slot,

        -- rose des vents à 16 secteurs (22.5° chacun) via un case robuste
        case
            when wind_direction_deg is null then null
            when wind_direction_deg >= 348.75 or wind_direction_deg < 11.25 then 'N'
            when wind_direction_deg < 33.75  then 'NNE'
            when wind_direction_deg < 56.25  then 'NE'
            when wind_direction_deg < 78.75  then 'ENE'
            when wind_direction_deg < 101.25 then 'E'
            when wind_direction_deg < 123.75 then 'ESE'
            when wind_direction_deg < 146.25 then 'SE'
            when wind_direction_deg < 168.75 then 'SSE'
            when wind_direction_deg < 191.25 then 'S'
            when wind_direction_deg < 213.75 then 'SSW'
            when wind_direction_deg < 236.25 then 'SW'
            when wind_direction_deg < 258.75 then 'WSW'
            when wind_direction_deg < 281.25 then 'W'
            when wind_direction_deg < 303.75 then 'WNW'
            when wind_direction_deg < 326.25 then 'NW'
            else 'NNW'
        end                                          as wind_direction_16pt

    from staged

)

select * from enriched