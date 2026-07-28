import dlt

pipeline = dlt.pipeline(pipeline_name="pioupiou_2176", destination="postgres", dataset_name="raw_pioupiou")

with pipeline.sql_client() as client:
    with client.execute_query(
        """
          select 
            -- time, 
            count(*) 
          from raw_pioupiou_staging.measurements 
          group by time 
          having count(*) > 1;
        """
        # "select count(*), min(time), max(time) from raw_pioupiou_staging.measurements;"
        # "select count(*), min(time), max(time) from raw_pioupiou.measurements;"
    ) as cursor:
        print(cursor.fetchall())