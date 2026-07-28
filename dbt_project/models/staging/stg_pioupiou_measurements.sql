with source as (

    select * from {{ source('raw_pioupiou', 'measurements') }}

),

renamed as (

    select
        station_id,
        (time)::timestamptz                        as measured_at,
        (wind_speed_avg)::numeric                  as wind_avg_kmh,
        (wind_speed_max)::numeric                  as wind_gust_kmh,
        (wind_speed_min)::numeric                  as wind_min_kmh,
        (wind_heading)::numeric                    as wind_direction_deg

    from source
    where time is not null

)

select * from renamed
